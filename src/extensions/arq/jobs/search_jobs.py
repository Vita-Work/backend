from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import with_session
from src.extensions.arq.middleware import arq_job_middleware
from src.logger import get_logger
from src.modules.search_jobs.repository import SearchJobWorkflowRunsRepository
from src.services import job_parsers as _job_parsers  # noqa: F401
from src.services.job_parsers.registry import get_registered_parser_names
from src.workflows.search_job.graph import get_search_job_graph

logger = get_logger("arq.jobs.search_jobs")


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
    workflow_run = await repository.get_by_id(workflow_run_id=UUID(workflow_run_id))
    if workflow_run is None:
        raise RuntimeError(f"Search job workflow run not found: {workflow_run_id}")

    workflow_run.status = "searching"
    workflow_run.error_message = None
    workflow_run.source_sites = get_registered_parser_names()
    await session.commit()

    try:
        graph = get_search_job_graph()
        result = await graph.ainvoke(
            {
                "status": "queued",
                "user_id": workflow_run.user_id,
                "onboarding_session_id": str(workflow_run.onboarding_session_id),
                "search_strategy_summary": workflow_run.search_strategy_summary,
                "hard_preferences": workflow_run.hard_preferences or [],
                "soft_preferences": workflow_run.soft_preferences or [],
                "source_sites": workflow_run.source_sites or [],
                "site_results": [],
                "unified_jobs": [],
                "batch_notes": [],
            }
        )
        final_jobs = result.get("final_jobs", [])
        site_results = result.get("site_results", [])
        batch_notes = result.get("batch_notes", [])
    except Exception as exc:
        workflow_run.status = "failed"
        workflow_run.error_message = str(exc)
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
    await session.commit()

    logger.info(
        "search_job_workflow_persisted",
        workflow_run_id=workflow_run.id,
        user_id=workflow_run.user_id,
        total_jobs_returned=workflow_run.total_jobs_returned,
    )
