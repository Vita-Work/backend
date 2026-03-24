from __future__ import annotations

from src.config import get_settings
from src.logger import get_logger
from src.services.job_search_tools import get_job_site_tools_service
from src.services.job_search_tools.service import ListSiteJobsArgs
from src.workflows.search_job.schemas import ListingCandidate, SiteAgentResult
from src.workflows.search_job.state import SearchJobState

logger = get_logger("workflows.search_job.parser")


async def dispatch_source_workers_node(state: SearchJobState) -> dict[str, object]:
    """Prepare the workflow for per-site deterministic parsing."""
    logger.info(
        "search_job_source_dispatch_started",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        source_sites_count=len(state.get("source_sites", [])),
    )
    return {"status": "searching"}


async def source_worker_node(state: SearchJobState) -> dict[str, object]:
    """Collect listing candidates for one site using the shared execution plan."""
    site_name = state["active_site"]
    plan = state["execution_plan"]
    log = logger.bind(
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        site=site_name,
    )
    log.info("search_job_site_parser_started")

    tool_service = get_job_site_tools_service(site_name)
    site_profile = tool_service.get_site_profile()
    if not site_profile.supports_native_query_search:
        log.info("search_job_site_parser_skipped", reason="native_query_search_not_supported")
        return {
            "site_results": [
                SiteAgentResult(
                    site=site_name,
                    status="skipped",
                    reason="native_query_search_not_supported",
                    notes=[site_profile.notes] if site_profile.notes else [],
                )
            ]
        }

    settings = get_settings()
    listings_by_url: dict[str, object] = {}
    listing_candidates: list[ListingCandidate] = []
    queries_used: list[str] = []
    notes: list[str] = []

    for query in plan.queries:
        try:
            results = await tool_service.list_site_jobs(
                args=ListSiteJobsArgs(
                    search_text=query,
                    locations=plan.locations,
                    remote_only=plan.remote_only,
                    salary_from=plan.salary_from,
                    max_pages=settings.search_job_listing_max_pages,
                    max_items=settings.search_job_listing_max_items,
                )
            )
        except Exception as exc:
            log.error("search_job_site_parser_failed", query=query, error=str(exc), exc_info=True)
            notes.append(f"query_failed:{query}")
            continue

        if query not in queries_used:
            queries_used.append(query)
        for listing in results:
            listings_by_url[listing.job_url] = listing
            listing_candidates.append(
                ListingCandidate(
                    site=site_name,
                    query=query,
                    job_url=listing.job_url,
                    title=listing.title,
                    company_name=listing.company_name,
                    location=listing.location,
                    salary_text=listing.salary_text,
                    published_at=listing.published_at,
                    company_url=listing.company_url,
                )
            )

    site_result = SiteAgentResult(
        site=site_name,
        status="ok",
        reason=None if listings_by_url else "no_listings_found",
        queries_used=queries_used,
        listings_seen=list(listings_by_url.values())[: settings.search_job_listing_max_items],
        selected_jobs=[],
        notes=notes,
    )
    log.info(
        "search_job_site_parser_completed",
        listings_seen_count=len(site_result.listings_seen),
        listing_candidates_count=len(listing_candidates),
    )
    return {
        "site_results": [site_result],
        "listing_candidates": listing_candidates,
    }
