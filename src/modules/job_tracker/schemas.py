from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.modules.job_tracker.constants import (
    TRACKED_JOB_ACTIVITY_TYPES,
    TRACKED_JOB_CONTACT_RELATIONS,
    TRACKED_JOB_INTERVIEW_FORMATS,
    TRACKED_JOB_PRIORITIES,
    TRACKED_JOB_SORT_OPTIONS,
    TRACKED_JOB_STATUSES,
)


class TrackedJobActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tracked_job_id: UUID
    user_id: str
    activity_type: str
    title: str | None = None
    body: str | None = None
    status_from: str | None = None
    status_to: str | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    event_at: datetime | None = None
    interview_format: str | None = None
    outcome: str | None = None
    details: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None


class TrackedJobContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tracked_job_id: UUID
    user_id: str
    name: str
    role: str | None = None
    company: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    relation_type: str
    last_contact_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None


class TrackedJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    source_type: str
    source_search_job_run_id: UUID | None = None
    source_job_url: str | None = None
    site: str | None = None
    title: str
    company_name: str
    location: str | None = None
    salary_text: str | None = None
    employment_type: str | None = None
    apply_url: str | None = None
    description_snapshot: str | None = None
    skills_snapshot: list[str] = Field(default_factory=list)
    fit_level: str | None = None
    why_apply_snapshot: str | None = None
    status: str
    priority: str
    deadline_at: datetime | None = None
    applied_at: datetime | None = None
    last_status_changed_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    notes_summary: str | None = None
    archived_at: datetime | None = None
    recommended_next_action: str | None = None
    created_at: datetime
    updated_at: datetime | None


class TrackedJobDetailResponse(TrackedJobResponse):
    activities: list[TrackedJobActivityResponse] = Field(default_factory=list)
    contacts: list[TrackedJobContactResponse] = Field(default_factory=list)


class CreateTrackedJobRequest(BaseModel):
    title: str
    company_name: str
    source_job_url: str | None = None
    site: str | None = "manual"
    location: str | None = None
    salary_text: str | None = None
    employment_type: str | None = None
    apply_url: str | None = None
    description_snapshot: str | None = None
    skills_snapshot: list[str] = Field(default_factory=list)
    fit_level: str | None = None
    why_apply_snapshot: str | None = None
    priority: str = "medium"
    deadline_at: datetime | None = None
    notes_summary: str | None = None

    @model_validator(mode="after")
    def validate_priority(self) -> CreateTrackedJobRequest:
        if self.priority not in TRACKED_JOB_PRIORITIES:
            raise ValueError("Invalid priority.")
        return self


class SaveTrackedJobFromSearchRunRequest(BaseModel):
    workflow_run_id: UUID
    job_url: str | None = None
    job_index: int | None = None

    @model_validator(mode="after")
    def validate_identifier(self) -> SaveTrackedJobFromSearchRunRequest:
        if self.job_url is None and self.job_index is None:
            raise ValueError("job_url or job_index is required.")
        return self


class UpdateTrackedJobRequest(BaseModel):
    title: str | None = None
    company_name: str | None = None
    source_job_url: str | None = None
    site: str | None = None
    location: str | None = None
    salary_text: str | None = None
    employment_type: str | None = None
    apply_url: str | None = None
    description_snapshot: str | None = None
    skills_snapshot: list[str] | None = None
    fit_level: str | None = None
    why_apply_snapshot: str | None = None
    priority: str | None = None
    deadline_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    notes_summary: str | None = None
    applied_at: datetime | None = None

    @model_validator(mode="after")
    def validate_priority(self) -> UpdateTrackedJobRequest:
        if self.priority is not None and self.priority not in TRACKED_JOB_PRIORITIES:
            raise ValueError("Invalid priority.")
        return self


class AdminUpdateTrackedJobRequest(UpdateTrackedJobRequest):
    status: str | None = None
    archived_at: datetime | None = None

    @model_validator(mode="after")
    def validate_status(self) -> AdminUpdateTrackedJobRequest:
        if self.status is not None and self.status not in TRACKED_JOB_STATUSES:
            raise ValueError("Invalid status.")
        return self


class UpdateTrackedJobStatusRequest(BaseModel):
    status: str

    @model_validator(mode="after")
    def validate_status(self) -> UpdateTrackedJobStatusRequest:
        if self.status not in TRACKED_JOB_STATUSES:
            raise ValueError("Invalid status.")
        return self


class CreateTrackedJobActivityRequest(BaseModel):
    activity_type: str
    title: str | None = None
    body: str | None = None
    due_at: datetime | None = None
    event_at: datetime | None = None
    interview_format: str | None = None
    outcome: str | None = None
    details: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_activity(self) -> CreateTrackedJobActivityRequest:
        if self.activity_type not in TRACKED_JOB_ACTIVITY_TYPES:
            raise ValueError("Invalid activity type.")
        if self.activity_type == "note" and not self.body:
            raise ValueError("Note activity requires body.")
        if self.activity_type == "follow_up" and self.due_at is None:
            raise ValueError("Follow-up activity requires due_at.")
        if self.activity_type == "interview":
            if self.event_at is None:
                raise ValueError("Interview activity requires event_at.")
            if self.interview_format and self.interview_format not in TRACKED_JOB_INTERVIEW_FORMATS:
                raise ValueError("Invalid interview format.")
        return self


class CreateTrackedJobContactRequest(BaseModel):
    name: str
    role: str | None = None
    company: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    relation_type: str = "other"
    last_contact_at: datetime | None = None
    next_follow_up_at: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_relation_type(self) -> CreateTrackedJobContactRequest:
        if self.relation_type not in TRACKED_JOB_CONTACT_RELATIONS:
            raise ValueError("Invalid relation type.")
        return self


class JobTrackerMetricsResponse(BaseModel):
    total_jobs: int = 0
    saved_jobs_count: int = 0
    applications_submitted: int = 0
    interviews_count: int = 0
    offers_count: int = 0
    rejections_count: int = 0
    conversion_saved_to_applied: float = 0.0
    conversion_applied_to_interview: float = 0.0
    conversion_interview_to_offer: float = 0.0
    jobs_by_status: dict[str, int] = Field(default_factory=dict)
    kanban_group_counts: dict[str, int] = Field(default_factory=dict)
    overdue_followups_count: int = 0
    average_days_in_stage: float = 0.0


class JobTrackerListQuery(BaseModel):
    status: str | None = None
    site: str | None = None
    priority: str | None = None
    has_follow_up: bool | None = None
    archived: bool = False
    search: str | None = None
    sort: str = "updated_at"

    @model_validator(mode="after")
    def validate_query(self) -> JobTrackerListQuery:
        if self.status is not None and self.status not in TRACKED_JOB_STATUSES:
            raise ValueError("Invalid status.")
        if self.priority is not None and self.priority not in TRACKED_JOB_PRIORITIES:
            raise ValueError("Invalid priority.")
        if self.sort not in TRACKED_JOB_SORT_OPTIONS:
            raise ValueError("Invalid sort option.")
        return self


class SaveTrackedJobFromSearchRunResponse(BaseModel):
    tracked_job: TrackedJobResponse
    already_saved: bool = False
    tracked_job_id: UUID
    tracker_status: str


class BulkUpdateTrackedJobsStatusRequest(BaseModel):
    tracked_job_ids: list[UUID] = Field(default_factory=list)
    status: str

    @model_validator(mode="after")
    def validate_payload(self) -> BulkUpdateTrackedJobsStatusRequest:
        if not self.tracked_job_ids:
            raise ValueError("tracked_job_ids is required.")
        if self.status not in TRACKED_JOB_STATUSES:
            raise ValueError("Invalid status.")
        return self


class BulkArchiveTrackedJobsRequest(BaseModel):
    tracked_job_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payload(self) -> BulkArchiveTrackedJobsRequest:
        if not self.tracked_job_ids:
            raise ValueError("tracked_job_ids is required.")
        return self


class JobTrackerDashboardResponse(BaseModel):
    tracker_totals: JobTrackerMetricsResponse
    upcoming_followups: list[TrackedJobActivityResponse] = Field(default_factory=list)
    overdue_followups: list[TrackedJobActivityResponse] = Field(default_factory=list)
    upcoming_interviews: list[TrackedJobActivityResponse] = Field(default_factory=list)
    recently_updated_jobs: list[TrackedJobResponse] = Field(default_factory=list)


class JobTrackerActivityFeedItemResponse(BaseModel):
    activity: TrackedJobActivityResponse
    tracked_job: TrackedJobResponse
