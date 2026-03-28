from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.workflows.search_job.schemas import SiteAgentResult, UnifiedJob


class StartSearchJobWorkflowRequest(BaseModel):
    """Start a search-job workflow from a completed onboarding session."""

    user_id: str
    monitoring_mode: bool = False


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
    monitoring_mode: bool = False
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
    current_internal_stage: str | None = None
    current_display_stage: str | None = None
    current_display_label: str | None = None
    current_display_description: str | None = None
    progress_percent: int | None = None
    progress_stage_index: int | None = None
    progress_stage_total: int | None = None
    billing_plan: str = "free"
    visible_jobs_count: int = 0
    hidden_jobs_count: int = 0
    viewer_job_limit: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_progress_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None


class SearchJobProgressEventResponse(BaseModel):
    workflow_run_id: UUID
    event_type: str
    internal_stage: str | None = None
    display_stage: str
    display_label: str
    display_description: str | None = None
    site: str | None = None
    progress_order: int | None = None
    display_icon_key: str | None = None
    display_color_key: str | None = None
    site_display_name: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
