from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LastFailedExtractionResponse(BaseModel):
    workflow_run_id: UUID
    ui_phase: str
    ui_label: str | None = None
    ui_description: str | None = None
    error_code: str | None = None
    retry_available: bool = False
    failed_at: datetime | None = None


class MeAppStateResponse(BaseModel):
    phase: str
    next_route: str
    needs_onboarding: bool
    has_active_onboarding_session: bool
    has_completed_onboarding: bool
    has_search_results: bool
    has_tracker_jobs: bool
    onboarding_session_id: UUID | None = None
    extraction_workflow_run_id: UUID | None = None
    search_job_workflow_run_id: UUID | None = None
    last_failed_extraction: LastFailedExtractionResponse | None = None
    is_new_user: bool = False
