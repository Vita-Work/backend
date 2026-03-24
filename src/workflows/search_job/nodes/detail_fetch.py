from __future__ import annotations

from src.logger import get_logger
from src.services.job_search_tools import get_job_site_tools_service
from src.workflows.search_job.schemas import SiteJobListing
from src.workflows.search_job.state import SearchJobState

logger = get_logger("workflows.search_job.detail_fetch")


async def dispatch_detail_fetch_node(state: SearchJobState) -> dict[str, object]:
    """Prepare detail expansion after listing dedupe."""
    logger.info(
        "search_job_detail_dispatch_started",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        deduped_listings_count=len(state.get("deduped_listings", [])),
    )
    return {"status": "fetching_details"}


async def detail_fetch_node(state: SearchJobState) -> dict[str, object]:
    """Fetch details for one site's deduped listing candidates."""
    site_name = state["detail_site"]
    candidates = state.get("detail_candidates", [])
    log = logger.bind(
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        site=site_name,
    )
    log.info("search_job_detail_fetch_started", detail_candidates_count=len(candidates))

    tool_service = get_job_site_tools_service(site_name)
    listing_inputs = [
        SiteJobListing(
            site=candidate.site,
            title=candidate.title,
            company_name=candidate.company_name,
            location=candidate.location,
            salary_text=candidate.salary_text,
            published_at=candidate.published_at,
            job_url=candidate.job_url,
            company_url=candidate.company_url,
        )
        for candidate in candidates
    ]

    source_queries_by_url = {
        candidate.job_url: list(candidate.source_queries) for candidate in candidates
    }
    try:
        detail_jobs = await tool_service.get_job_details_from_listings(listings=listing_inputs)
    except Exception as exc:
        log.error("search_job_detail_fetch_failed", error=str(exc), exc_info=True)
        return {"batch_notes": [f"detail_fetch_failed:{site_name}"]}

    enriched_details = []
    for detail in detail_jobs:
        raw_meta = dict(detail.raw_meta)
        raw_meta["source_queries"] = source_queries_by_url.get(detail.job_url, [])
        enriched_details.append(detail.model_copy(update={"raw_meta": raw_meta}))

    log.info("search_job_detail_fetch_completed", detailed_jobs_count=len(enriched_details))
    return {"detailed_jobs": enriched_details}
