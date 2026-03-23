from __future__ import annotations

from src.config import get_settings
from src.extensions.dspy import get_dspy_search_setup_service
from src.logger import get_logger
from src.workflows.search_job.schemas import SearchExecutionPlan
from src.workflows.search_job.state import SearchJobState

logger = get_logger("workflows.search_job.plan")


async def plan_search_execution_node(state: SearchJobState) -> dict[str, object]:
    """Build the runtime search execution plan for the current run."""
    log = logger.bind(
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
    )
    log.info("search_job_plan_started")

    service = get_dspy_search_setup_service()
    plan = await service.build_search_job_execution_plan(
        search_strategy_summary=state["search_strategy_summary"],
        hard_preferences=state["hard_preferences"],
        soft_preferences=state["soft_preferences"],
        available_sites=state["source_sites"],
    )

    settings = get_settings()
    plan = _normalize_plan(
        plan=SearchExecutionPlan.model_validate(plan.model_dump(mode="json")),
        available_sites=state["source_sites"],
        max_queries=settings.search_job_plan_max_queries,
        fallback_query=state["search_strategy_summary"],
    )

    log.info(
        "search_job_plan_completed",
        queries_count=len(plan.queries),
        target_sites_count=len(plan.target_sites),
    )
    return {
        "status": "planning",
        "execution_plan": plan,
        "source_sites": plan.target_sites,
        "search_model": service.model_name,
    }


def _normalize_plan(
    *,
    plan: SearchExecutionPlan,
    available_sites: list[str],
    max_queries: int,
    fallback_query: str,
) -> SearchExecutionPlan:
    normalized_queries = list(
        dict.fromkeys(
            query.strip() for query in plan.queries if isinstance(query, str) and query.strip()
        )
    )
    normalized_sites = [site for site in plan.target_sites if site in set(available_sites)]

    if not normalized_queries:
        fallback = " ".join(fallback_query.split())[:160].strip()
        if fallback:
            normalized_queries = [fallback]

    if not normalized_sites:
        normalized_sites = list(available_sites)

    return plan.model_copy(
        update={
            "queries": normalized_queries[:max_queries],
            "include_keywords": [
                item.strip()
                for item in plan.include_keywords
                if isinstance(item, str) and item.strip()
            ],
            "exclude_keywords": [
                item.strip()
                for item in plan.exclude_keywords
                if isinstance(item, str) and item.strip()
            ],
            "locations": [
                item.strip() for item in plan.locations if isinstance(item, str) and item.strip()
            ],
            "target_sites": normalized_sites,
            "notes": [
                item.strip() for item in plan.notes if isinstance(item, str) and item.strip()
            ],
        }
    )
