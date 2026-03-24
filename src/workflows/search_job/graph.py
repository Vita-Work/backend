from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from src.workflows.search_job.nodes import (
    detail_dedupe_node,
    detail_fetch_node,
    dispatch_detail_fetch_node,
    dispatch_source_workers_node,
    dispatch_unification_node,
    finalize_search_results_node,
    listing_dedupe_node,
    plan_search_execution_node,
    source_worker_node,
    unify_jobs_batch_node,
)
from src.workflows.search_job.schemas import DetailFetchCandidate
from src.workflows.search_job.state import SearchJobState


def build_search_job_graph():
    """Build the job-search workflow graph."""
    graph = StateGraph(SearchJobState)
    graph.add_node("plan_search_execution", plan_search_execution_node)
    graph.add_node("dispatch_source_workers", dispatch_source_workers_node)
    graph.add_node("source_worker", source_worker_node)
    graph.add_node("listing_dedupe", listing_dedupe_node, defer=True)
    graph.add_node("dispatch_detail_fetch", dispatch_detail_fetch_node)
    graph.add_node("detail_fetch", detail_fetch_node)
    graph.add_node("detail_dedupe", detail_dedupe_node, defer=True)
    graph.add_node("dispatch_unification", dispatch_unification_node)
    graph.add_node("unify_jobs_batch", unify_jobs_batch_node)
    graph.add_node("finalize_search_results", finalize_search_results_node, defer=True)

    graph.add_edge(START, "plan_search_execution")
    graph.add_edge("plan_search_execution", "dispatch_source_workers")
    graph.add_conditional_edges("dispatch_source_workers", _route_source_workers)
    graph.add_edge("source_worker", "listing_dedupe")
    graph.add_edge("listing_dedupe", "dispatch_detail_fetch")
    graph.add_conditional_edges("dispatch_detail_fetch", _route_detail_fetch_batches)
    graph.add_edge("detail_fetch", "detail_dedupe")
    graph.add_edge("detail_dedupe", "dispatch_unification")
    graph.add_conditional_edges("dispatch_unification", _route_unification_batches)
    graph.add_edge("unify_jobs_batch", "finalize_search_results")
    graph.add_edge("finalize_search_results", END)
    return graph.compile()


def _route_source_workers(state: SearchJobState):
    if not state.get("source_sites"):
        return "listing_dedupe"
    return [
        Send(
            "source_worker",
            {
                "user_id": state["user_id"],
                "onboarding_session_id": state["onboarding_session_id"],
                "search_strategy_summary": state["search_strategy_summary"],
                "hard_preferences": state["hard_preferences"],
                "soft_preferences": state["soft_preferences"],
                "execution_plan": state["execution_plan"],
                "active_site": site_name,
            },
        )
        for site_name in state["source_sites"]
    ]


def _route_detail_fetch_batches(state: SearchJobState):
    grouped = _group_detail_candidates_by_site(state.get("deduped_listings", []))
    if not grouped:
        return "dispatch_unification"
    return [
        Send(
            "detail_fetch",
            {
                "user_id": state["user_id"],
                "onboarding_session_id": state["onboarding_session_id"],
                "detail_site": site_name,
                "detail_candidates": candidates,
            },
        )
        for site_name, candidates in grouped.items()
    ]


def _route_unification_batches(state: SearchJobState):
    batch_jobs = _collect_batch_jobs(state)
    if not batch_jobs:
        return "finalize_search_results"
    return [
        Send(
            "unify_jobs_batch",
            {
                "user_id": state["user_id"],
                "onboarding_session_id": state["onboarding_session_id"],
                "search_strategy_summary": state["search_strategy_summary"],
                "hard_preferences": state["hard_preferences"],
                "soft_preferences": state["soft_preferences"],
                "batch_jobs": batch,
            },
        )
        for batch in batch_jobs
    ]


def _collect_batch_jobs(state: SearchJobState) -> list[list[dict[str, object]]]:
    from src.config import get_settings

    selected_jobs = [
        {
            **job.model_dump(mode="json"),
            "source_queries": list(job.raw_meta.get("source_queries", [])),
        }
        for job in state.get("deduped_details", [])
    ]

    settings = get_settings()
    limited_jobs = selected_jobs[: settings.search_job_unified_max_jobs]
    batch_size = max(1, settings.search_job_unified_batch_size)
    return [
        limited_jobs[index : index + batch_size]
        for index in range(0, len(limited_jobs), batch_size)
    ]


def _group_detail_candidates_by_site(
    candidates: list[DetailFetchCandidate],
) -> dict[str, list[DetailFetchCandidate]]:
    grouped: dict[str, list[DetailFetchCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.site, []).append(candidate)
    return grouped


@lru_cache(maxsize=1)
def get_search_job_graph():
    """Return the shared compiled search-job graph."""
    return build_search_job_graph()
