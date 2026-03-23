from __future__ import annotations

from collections import Counter

from src.config import get_settings
from src.extensions.gemini import get_gemini_job_search_service
from src.extensions.langchain import get_langchain_search_job_service
from src.logger import get_logger
from src.workflows.search_job.schemas import SiteAgentResult, UnifiedJob
from src.workflows.search_job.state import SearchJobState

logger = get_logger("workflows.search_job")


async def dispatch_source_workers_node(state: SearchJobState) -> dict[str, object]:
    """Prepare the search-job workflow for per-site fan-out."""
    logger.info(
        "search_job_source_dispatch_started",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        source_sites_count=len(state.get("source_sites", [])),
    )
    return {
        "status": "searching",
        "search_model": get_settings().gemini_model,
    }


async def source_worker_node(state: SearchJobState) -> dict[str, object]:
    """Run one per-site search agent."""
    site_name = state["active_site"]
    log = logger.bind(
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        site=site_name,
    )
    log.info("search_job_site_worker_started")

    service = get_langchain_search_job_service()
    try:
        site_result = await service.run_site_agent(
            site_name=site_name,
            search_strategy_summary=state["search_strategy_summary"],
            hard_preferences=state["hard_preferences"],
            soft_preferences=state["soft_preferences"],
        )
    except Exception as exc:
        log.error("search_job_site_worker_failed", error=str(exc), exc_info=True)
        site_result = SiteAgentResult(
            site=site_name,
            status="failed",
            reason="site_worker_failed",
            notes=[str(exc)],
        )

    log.info(
        "search_job_site_worker_completed",
        status=site_result.status,
        selected_jobs_count=len(site_result.selected_jobs),
    )
    return {"site_results": [site_result]}


async def dispatch_unification_node(state: SearchJobState) -> dict[str, object]:
    """Prepare batch unification after all site workers finish."""
    total_selected_jobs = sum(len(result.selected_jobs) for result in state.get("site_results", []))
    logger.info(
        "search_job_unification_dispatch_started",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        site_results_count=len(state.get("site_results", [])),
        selected_jobs_count=total_selected_jobs,
    )
    return {
        "status": "unifying",
        "unification_model": get_settings().gemini_model,
    }


async def unify_jobs_batch_node(state: SearchJobState) -> dict[str, object]:
    """Annotate one batch of selected jobs into the unified schema."""
    service = get_gemini_job_search_service()
    batch_jobs = state.get("batch_jobs", [])
    logger.info(
        "search_job_unification_batch_started",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        batch_size=len(batch_jobs),
    )
    try:
        result = await service.unify_jobs_batch(
            search_strategy_summary=state["search_strategy_summary"],
            hard_preferences=state["hard_preferences"],
            soft_preferences=state["soft_preferences"],
            batch_jobs=batch_jobs,
        )
        unified_jobs = result.jobs
        batch_notes = result.notes
    except Exception as exc:
        logger.error(
            "search_job_unification_batch_failed",
            user_id=state["user_id"],
            onboarding_session_id=state["onboarding_session_id"],
            batch_size=len(batch_jobs),
            error=str(exc),
            exc_info=True,
        )
        unified_jobs = []
        batch_notes = [f"Batch unification failed: {exc}"]
    logger.info(
        "search_job_unification_batch_completed",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        batch_size=len(batch_jobs),
        unified_jobs_count=len(unified_jobs),
    )
    return {
        "unified_jobs": unified_jobs,
        "batch_notes": batch_notes,
    }


async def finalize_search_results_node(state: SearchJobState) -> dict[str, object]:
    """Finalize and summarize the full search-job workflow output."""
    deduped_jobs = _dedupe_and_sort_jobs(state.get("unified_jobs", []))
    settings = get_settings()
    final_jobs = deduped_jobs[: settings.search_job_unified_max_jobs]
    summary_markdown = _build_summary_markdown(
        site_results=state.get("site_results", []),
        jobs=final_jobs,
        notes=state.get("batch_notes", []),
    )
    logger.info(
        "search_job_finalize_completed",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        total_jobs_returned=len(final_jobs),
    )
    return {
        "status": "completed",
        "summary_markdown": summary_markdown,
        "final_jobs": final_jobs,
    }


def _dedupe_and_sort_jobs(jobs: list[UnifiedJob]) -> list[UnifiedJob]:
    unique_jobs: dict[tuple[str, str], UnifiedJob] = {}
    for job in jobs:
        key = (job.site, job.job_url)
        current = unique_jobs.get(key)
        if current is None or _fit_rank(job.fit_level) > _fit_rank(current.fit_level):
            unique_jobs[key] = job

    return sorted(
        unique_jobs.values(),
        key=lambda job: (
            -_fit_rank(job.fit_level),
            (job.title or "").lower(),
            (job.company_name or "").lower(),
        ),
    )


def _fit_rank(fit_level: str) -> int:
    return {"high": 3, "middle": 2, "low": 1}.get(fit_level, 0)


def _build_summary_markdown(
    *,
    site_results: list[SiteAgentResult],
    jobs: list[UnifiedJob],
    notes: list[str],
) -> str:
    skipped_sites = [result.site for result in site_results if result.status == "skipped"]
    fit_counts = Counter(job.fit_level for job in jobs)
    top_jobs = jobs[:10]
    top_lines = [
        (
            f"- [{job.fit_level}] {job.title or 'Unknown role'} at "
            f"{job.company_name or 'Unknown company'} ({job.site})"
            f": {job.why_apply}"
        )
        for job in top_jobs
    ]
    notes_block = "\n".join(f"- {note}" for note in notes[:10]) if notes else "- None"
    skipped_block = "\n".join(f"- {site}" for site in skipped_sites) if skipped_sites else "- None"
    top_block = "\n".join(top_lines) if top_lines else "- None"
    return (
        "# Search Job Summary\n\n"
        f"- Site results: {len(site_results)}\n"
        f"- Unified jobs returned: {len(jobs)}\n"
        f"- High fit: {fit_counts.get('high', 0)}\n"
        f"- Middle fit: {fit_counts.get('middle', 0)}\n"
        f"- Low fit: {fit_counts.get('low', 0)}\n\n"
        "## Top Matches\n"
        f"{top_block}\n\n"
        "## Skipped Sites\n"
        f"{skipped_block}\n\n"
        "## Notes\n"
        f"{notes_block}"
    )
