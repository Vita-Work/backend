from operator import add
from typing import Annotated, Literal, NotRequired, TypedDict

from src.workflows.search_job.schemas import (
    DetailFetchCandidate,
    ListingCandidate,
    SearchExecutionPlan,
    SiteAgentResult,
    SiteJobDetail,
    UnifiedJob,
)

SearchJobStatus = Literal[
    "queued",
    "planning",
    "searching",
    "deduping",
    "fetching_details",
    "unifying",
    "completed",
    "failed",
]


class SearchJobState(TypedDict):
    """Unified state for the background search-job workflow."""

    status: SearchJobStatus

    user_id: str
    onboarding_session_id: str
    search_strategy_summary: str
    hard_preferences: list[str]
    soft_preferences: list[str]
    source_sites: list[str]
    monitoring_mode: bool
    seen_job_urls: list[str]
    seen_job_fingerprints: list[str]

    execution_plan: NotRequired[SearchExecutionPlan]
    active_site: NotRequired[str]
    detail_site: NotRequired[str]
    detail_candidates: NotRequired[list[DetailFetchCandidate]]
    batch_jobs: NotRequired[list[dict[str, object]]]

    site_results: Annotated[list[SiteAgentResult], add]
    listing_candidates: Annotated[list[ListingCandidate], add]
    detailed_jobs: Annotated[list[SiteJobDetail], add]
    unified_jobs: Annotated[list[UnifiedJob], add]
    batch_notes: Annotated[list[str], add]

    deduped_listings: NotRequired[list[DetailFetchCandidate]]
    deduped_details: NotRequired[list[SiteJobDetail]]
    final_site_results: NotRequired[list[SiteAgentResult]]
    final_jobs: NotRequired[list[UnifiedJob]]
    summary_markdown: NotRequired[str]
    search_model: NotRequired[str]
    unification_model: NotRequired[str]
