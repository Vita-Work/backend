from operator import add
from typing import Annotated, Literal, NotRequired, TypedDict

from src.workflows.search_job.schemas import SiteAgentResult, UnifiedJob

SearchJobStatus = Literal["queued", "searching", "unifying", "completed", "failed"]


class SearchJobState(TypedDict):
    """Unified state for the background search-job workflow."""

    status: SearchJobStatus

    user_id: str
    onboarding_session_id: str
    search_strategy_summary: str
    hard_preferences: list[str]
    soft_preferences: list[str]
    source_sites: list[str]

    active_site: NotRequired[str]
    batch_jobs: NotRequired[list[dict[str, object]]]

    site_results: Annotated[list[SiteAgentResult], add]
    unified_jobs: Annotated[list[UnifiedJob], add]
    batch_notes: Annotated[list[str], add]

    final_jobs: NotRequired[list[UnifiedJob]]
    summary_markdown: NotRequired[str]
    search_model: NotRequired[str]
    unification_model: NotRequired[str]
