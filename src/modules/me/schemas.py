from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


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
    is_new_user: bool = False
