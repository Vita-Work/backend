from __future__ import annotations

from src.config import get_settings
from src.extensions.gemini import get_gemini_job_search_service
from src.logger import get_logger
from src.workflows.search_job.state import SearchJobState

logger = get_logger("workflows.search_job.rank")


async def dispatch_unification_node(state: SearchJobState) -> dict[str, object]:
    """Prepare batch ranking and enrichment after detail dedupe."""
    logger.info(
        "search_job_unification_dispatch_started",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        deduped_details_count=len(state.get("deduped_details", [])),
    )
    return {
        "status": "unifying",
        "unification_model": get_settings().gemini_model,
    }


async def unify_jobs_batch_node(state: SearchJobState) -> dict[str, object]:
    """Annotate one batch of detailed jobs into the final unified schema."""
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
