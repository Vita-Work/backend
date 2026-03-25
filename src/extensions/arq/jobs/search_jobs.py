from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import with_session
from src.extensions.arq.middleware import arq_job_middleware
from src.logger import get_logger
from src.modules.search_jobs.progress import update_search_progress
from src.modules.search_jobs.repository import (
    SearchJobSeenJobsRepository,
    SearchJobWorkflowRunsRepository,
)
from src.services import job_parsers as _job_parsers  # noqa: F401
from src.services.job_parsers.registry import get_registered_parser_names
from src.workflows.search_job.graph import get_search_job_graph

logger = get_logger("arq.jobs.search_jobs")


def _merge_graph_update(state: dict[str, object], update: Mapping[str, object]) -> None:
    for key, value in update.items():
        if isinstance(value, list):
            existing = state.get(key)
            if isinstance(existing, list):
                state[key] = [*existing, *value]
            else:
                state[key] = list(value)
            continue
        state[key] = value


def _coerce_node_updates(chunk: object) -> dict[str, dict[str, object]]:
    if isinstance(chunk, tuple) and len(chunk) == 2:
        _, payload = chunk
        chunk = payload
    if not isinstance(chunk, Mapping):
        return {}

    node_updates: dict[str, dict[str, object]] = {}
    for node_name, payload in chunk.items():
        if isinstance(payload, Mapping):
            node_updates[str(node_name)] = dict(payload)
    return node_updates


def _stage_for_node(node_name: str, update: Mapping[str, object]) -> tuple[str, str]:
    status = update.get("status")
    if isinstance(status, str):
        return status, "phase_changed"
    if node_name in {"plan_search_execution"}:
        return "planning", "step_completed"
    if node_name in {"dispatch_source_workers", "source_worker"}:
        return "searching", "site_activity"
    if node_name in {"listing_dedupe", "detail_dedupe"}:
        return "deduping", "step_completed"
    if node_name in {"dispatch_detail_fetch", "detail_fetch"}:
        return "fetching_details", "site_activity"
    if node_name in {"dispatch_unification", "unify_jobs_batch"}:
        return "unifying", "step_completed"
    if node_name in {"finalize_search_results"}:
        return "completed", "jobs_ready"
    return "searching", "step_completed"


def _site_for_node(node_name: str, update: Mapping[str, object]) -> str | None:
    if node_name == "source_worker":
        site_results = update.get("site_results")
        if isinstance(site_results, list) and site_results:
            first = site_results[0]
            site = getattr(first, "site", None)
            if isinstance(site, str):
                return site
    if node_name == "detail_fetch":
        detailed_jobs = update.get("detailed_jobs")
        if isinstance(detailed_jobs, list) and detailed_jobs:
            first = detailed_jobs[0]
            site = getattr(first, "site", None)
            if isinstance(site, str):
                return site
    return None


@arq_job_middleware
@with_session
async def process_search_job_workflow(
    ctx: dict,
    workflow_run_id: str,
    *,
    session: AsyncSession,
) -> None:
    """Run the search-job workflow in the background and persist the result."""
    _ = ctx
    repository = SearchJobWorkflowRunsRepository(session=session)
    seen_jobs_repository = SearchJobSeenJobsRepository(session=session)
    workflow_run = await repository.get_by_id(workflow_run_id=UUID(workflow_run_id))
    if workflow_run is None:
        raise RuntimeError(f"Search job workflow run not found: {workflow_run_id}")

    workflow_run.status = "searching"
    workflow_run.error_message = None
    workflow_run.source_sites = get_registered_parser_names()
    update_search_progress(
        repository=repository,
        workflow_run=workflow_run,
        event_type="phase_changed",
        internal_stage="planning",
        payload={"source_sites": workflow_run.source_sites or []},
    )
    await session.commit()

    try:
        seen_job_urls: list[str] = []
        seen_job_fingerprints: list[str] = []
        if workflow_run.monitoring_mode:
            seen_job_urls = await seen_jobs_repository.list_seen_job_urls(
                user_id=workflow_run.user_id
            )
            seen_job_fingerprints = await seen_jobs_repository.list_seen_job_fingerprints(
                user_id=workflow_run.user_id
            )

        graph = get_search_job_graph()
        initial_state = {
            "status": "queued",
            "user_id": workflow_run.user_id,
            "onboarding_session_id": str(workflow_run.onboarding_session_id),
            "search_strategy_summary": workflow_run.search_strategy_summary,
            "hard_preferences": workflow_run.hard_preferences or [],
            "soft_preferences": workflow_run.soft_preferences or [],
            "source_sites": workflow_run.source_sites or [],
            "monitoring_mode": workflow_run.monitoring_mode,
            "seen_job_urls": seen_job_urls,
            "seen_job_fingerprints": seen_job_fingerprints,
            "site_results": [],
            "listing_candidates": [],
            "detailed_jobs": [],
            "unified_jobs": [],
            "batch_notes": [],
        }
        result: dict[str, object] = dict(initial_state)
        async for chunk in graph.astream(initial_state, stream_mode="updates"):
            node_updates = _coerce_node_updates(chunk)
            for node_name, update in node_updates.items():
                _merge_graph_update(result, update)
                internal_stage, event_type = _stage_for_node(node_name, update)
                site = _site_for_node(node_name, update)
                update_search_progress(
                    repository=repository,
                    workflow_run=workflow_run,
                    event_type=event_type,
                    internal_stage=internal_stage,
                    site=site,
                    payload={
                        "node_name": node_name,
                        "keys": list(update.keys()),
                    },
                )
                if internal_stage != "completed":
                    workflow_run.status = internal_stage
                await session.commit()

        final_jobs = result.get("final_jobs", [])
        site_results = result.get("final_site_results", result.get("site_results", []))
        batch_notes = result.get("batch_notes", [])
    except Exception as exc:
        workflow_run.status = "failed"
        workflow_run.error_message = str(exc)
        update_search_progress(
            repository=repository,
            workflow_run=workflow_run,
            event_type="error",
            internal_stage="failed",
            payload={"error": str(exc)},
        )
        await session.commit()
        logger.error(
            "search_job_workflow_failed",
            workflow_run_id=workflow_run.id,
            user_id=workflow_run.user_id,
            error=str(exc),
            exc_info=True,
        )
        raise

    workflow_run.status = "completed"
    await seen_jobs_repository.record_delivered_jobs(
        user_id=workflow_run.user_id,
        workflow_run_id=workflow_run.id,
        jobs=final_jobs,
    )
    workflow_run.total_site_results = len(site_results)
    workflow_run.total_jobs_found = sum(len(result.selected_jobs) for result in site_results)
    workflow_run.total_jobs_returned = len(final_jobs)
    workflow_run.summary_markdown = result.get("summary_markdown")
    workflow_run.jobs = [job.model_dump(mode="json") for job in final_jobs]
    workflow_run.site_results = [
        site_result.model_dump(mode="json") for site_result in site_results
    ]
    workflow_run.notes = list(batch_notes)
    workflow_run.search_model = result.get("search_model")
    workflow_run.unification_model = result.get("unification_model")
    workflow_run.error_message = None
    update_search_progress(
        repository=repository,
        workflow_run=workflow_run,
        event_type="jobs_ready",
        internal_stage="completed",
        payload={"total_jobs_returned": workflow_run.total_jobs_returned},
    )
    await session.commit()

    logger.info(
        "search_job_workflow_persisted",
        workflow_run_id=workflow_run.id,
        user_id=workflow_run.user_id,
        total_jobs_returned=workflow_run.total_jobs_returned,
    )
