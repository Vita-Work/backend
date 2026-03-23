from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.workflows.search_job.schemas import SiteAgentResult, UnifiedJob


class StartSearchJobWorkflowRequest(BaseModel):
    """Start a search-job workflow from a completed onboarding session."""

    user_id: str


class SearchJobWorkflowRunResponse(BaseModel):
    """Search-job workflow API response."""

    model_config = ConfigDict(from_attributes=True)

    workflow_run_id: UUID
    onboarding_session_id: UUID
    user_id: str
    status: str
    search_strategy_summary: str
    hard_preferences: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    source_sites: list[str] = Field(default_factory=list)
    total_site_results: int = 0
    total_jobs_found: int = 0
    total_jobs_returned: int = 0
    summary_markdown: str | None = None
    jobs: list[UnifiedJob] = Field(default_factory=list)
    site_results: list[SiteAgentResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    search_model: str | None = None
    unification_model: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime | None
