from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from src.modules.auth.security import utcnow
from src.modules.job_tracker.constants import (
    TRACKED_JOB_ACTIVITY_FOLLOW_UP,
    TRACKED_JOB_ACTIVITY_INTERVIEW,
    TRACKED_JOB_ACTIVITY_STATUS_CHANGE,
    TRACKED_JOB_PRIORITY_MEDIUM,
    TRACKED_JOB_SOURCE_MANUAL,
    TRACKED_JOB_STATUS_APPLIED_AND_BEYOND,
    TRACKED_JOB_STATUS_ARCHIVED,
    TRACKED_JOB_STATUS_INTERVIEW_STAGES,
    TRACKED_JOB_STATUS_OFFER,
    TRACKED_JOB_STATUS_REJECTED,
    TRACKED_JOB_STATUS_SAVED,
)
from src.modules.job_tracker.models import TrackedJob, TrackedJobActivity, TrackedJobContact
from src.modules.job_tracker.schemas import (
    CreateTrackedJobActivityRequest,
    CreateTrackedJobContactRequest,
    CreateTrackedJobRequest,
    JobTrackerMetricsResponse,
    TrackedJobActivityResponse,
    TrackedJobContactResponse,
    TrackedJobDetailResponse,
    TrackedJobResponse,
    UpdateTrackedJobRequest,
)
from src.workflows.search_job.schemas import UnifiedJob


def normalize_job_url(url: str | None) -> str | None:
    if url is None:
        return None
    normalized = url.strip()
    if not normalized:
        return None
    split = urlsplit(normalized)
    path = split.path.rstrip("/") or split.path
    return urlunsplit((split.scheme, split.netloc.lower(), path, split.query, ""))


def build_tracked_job_detail(
    *,
    tracked_job: TrackedJob,
    activities: list[TrackedJobActivity],
    contacts: list[TrackedJobContact],
) -> TrackedJobDetailResponse:
    payload = TrackedJobResponse.model_validate(tracked_job).model_dump()
    payload["activities"] = [TrackedJobActivityResponse.model_validate(item) for item in activities]
    payload["contacts"] = [TrackedJobContactResponse.model_validate(item) for item in contacts]
    return TrackedJobDetailResponse.model_validate(payload)


def apply_job_updates(*, tracked_job: TrackedJob, payload: UpdateTrackedJobRequest) -> None:
    for field in (
        "title",
        "company_name",
        "site",
        "location",
        "salary_text",
        "employment_type",
        "apply_url",
        "description_snapshot",
        "fit_level",
        "why_apply_snapshot",
        "priority",
        "deadline_at",
        "next_follow_up_at",
        "notes_summary",
        "applied_at",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(tracked_job, field, value)

    if payload.skills_snapshot is not None:
        tracked_job.skills_snapshot = payload.skills_snapshot
    if payload.source_job_url is not None:
        tracked_job.source_job_url = normalize_job_url(payload.source_job_url)


def create_tracked_job_from_manual_payload(
    *,
    user_id: str,
    payload: CreateTrackedJobRequest,
) -> dict:
    return {
        "user_id": user_id,
        "source_type": TRACKED_JOB_SOURCE_MANUAL,
        "source_search_job_run_id": None,
        "source_job_url": normalize_job_url(payload.source_job_url),
        "site": (payload.site or "manual").strip() or "manual",
        "title": payload.title.strip(),
        "company_name": payload.company_name.strip(),
        "location": payload.location,
        "salary_text": payload.salary_text,
        "employment_type": payload.employment_type,
        "apply_url": payload.apply_url,
        "description_snapshot": payload.description_snapshot,
        "skills_snapshot": payload.skills_snapshot,
        "fit_level": payload.fit_level,
        "why_apply_snapshot": payload.why_apply_snapshot,
        "status": TRACKED_JOB_STATUS_SAVED,
        "priority": payload.priority or TRACKED_JOB_PRIORITY_MEDIUM,
        "deadline_at": payload.deadline_at,
        "applied_at": None,
        "last_status_changed_at": utcnow(),
        "next_follow_up_at": None,
        "notes_summary": payload.notes_summary,
        "archived_at": None,
    }


def create_tracked_job_from_unified_job(
    *,
    user_id: str,
    workflow_run_id: UUID,
    job: UnifiedJob,
) -> dict:
    normalized_job_url = normalize_job_url(job.job_url)
    return {
        "user_id": user_id,
        "source_type": "search_result",
        "source_search_job_run_id": workflow_run_id,
        "source_job_url": normalized_job_url,
        "site": job.site,
        "title": job.title or "Untitled role",
        "company_name": job.company_name or "Unknown company",
        "location": job.location,
        "salary_text": job.salary_text,
        "employment_type": job.employment_type,
        "apply_url": job.apply_url,
        "description_snapshot": job.description,
        "skills_snapshot": job.skills,
        "fit_level": job.fit_level,
        "why_apply_snapshot": job.why_apply,
        "status": TRACKED_JOB_STATUS_SAVED,
        "priority": TRACKED_JOB_PRIORITY_MEDIUM,
        "deadline_at": None,
        "applied_at": None,
        "last_status_changed_at": utcnow(),
        "next_follow_up_at": None,
        "notes_summary": None,
        "archived_at": None,
    }


def create_status_change_activity_payload(
    *,
    user_id: str,
    tracked_job_id: UUID,
    from_status: str | None,
    to_status: str,
) -> dict:
    return {
        "tracked_job_id": tracked_job_id,
        "user_id": user_id,
        "activity_type": TRACKED_JOB_ACTIVITY_STATUS_CHANGE,
        "title": f"Status changed to {to_status}",
        "body": None,
        "status_from": from_status,
        "status_to": to_status,
        "due_at": None,
        "completed_at": None,
        "event_at": utcnow(),
        "interview_format": None,
        "outcome": None,
        "details": {},
    }


def create_activity_payload(
    *,
    user_id: str,
    tracked_job_id: UUID,
    payload: CreateTrackedJobActivityRequest,
) -> dict:
    return {
        "tracked_job_id": tracked_job_id,
        "user_id": user_id,
        "activity_type": payload.activity_type,
        "title": payload.title,
        "body": payload.body,
        "status_from": None,
        "status_to": None,
        "due_at": payload.due_at,
        "completed_at": None,
        "event_at": payload.event_at or utcnow(),
        "interview_format": payload.interview_format,
        "outcome": payload.outcome,
        "details": payload.details,
    }


def create_contact_payload(
    *,
    user_id: str,
    tracked_job_id: UUID,
    payload: CreateTrackedJobContactRequest,
) -> dict:
    return {
        "tracked_job_id": tracked_job_id,
        "user_id": user_id,
        "name": payload.name.strip(),
        "role": payload.role,
        "company": payload.company,
        "email": payload.email,
        "linkedin_url": payload.linkedin_url,
        "relation_type": payload.relation_type,
        "last_contact_at": payload.last_contact_at,
        "next_follow_up_at": payload.next_follow_up_at,
        "notes": payload.notes,
    }


def apply_status_transition(*, tracked_job: TrackedJob, status: str) -> None:
    tracked_job.status = status
    tracked_job.last_status_changed_at = utcnow()
    if status in TRACKED_JOB_STATUS_APPLIED_AND_BEYOND and tracked_job.applied_at is None:
        tracked_job.applied_at = utcnow()
    if status == TRACKED_JOB_STATUS_ARCHIVED:
        tracked_job.archived_at = utcnow()
    elif tracked_job.archived_at is not None:
        tracked_job.archived_at = None


def compute_job_tracker_metrics(
    *,
    jobs: Iterable[TrackedJob],
    activities: Iterable[TrackedJobActivity],
    now: datetime | None = None,
) -> JobTrackerMetricsResponse:
    now = now or utcnow()
    job_list = list(jobs)
    activity_list = list(activities)

    jobs_by_status = Counter(job.status for job in job_list)
    jobs_reached_applied = {
        str(job.id)
        for job in job_list
        if job.applied_at is not None or job.status in TRACKED_JOB_STATUS_APPLIED_AND_BEYOND
    }
    jobs_reached_applied.update(
        str(activity.tracked_job_id)
        for activity in activity_list
        if activity.activity_type == TRACKED_JOB_ACTIVITY_STATUS_CHANGE
        and activity.status_to in TRACKED_JOB_STATUS_APPLIED_AND_BEYOND
    )

    jobs_reached_interview = {
        str(job.id) for job in job_list if job.status in TRACKED_JOB_STATUS_INTERVIEW_STAGES
    }
    jobs_reached_interview.update(
        str(activity.tracked_job_id)
        for activity in activity_list
        if activity.activity_type == TRACKED_JOB_ACTIVITY_INTERVIEW
    )
    jobs_reached_interview.update(
        str(activity.tracked_job_id)
        for activity in activity_list
        if activity.activity_type == TRACKED_JOB_ACTIVITY_STATUS_CHANGE
        and activity.status_to in TRACKED_JOB_STATUS_INTERVIEW_STAGES
    )

    open_followups = [
        activity
        for activity in activity_list
        if activity.activity_type == TRACKED_JOB_ACTIVITY_FOLLOW_UP
        and activity.completed_at is None
    ]
    overdue_followups_count = sum(1 for item in open_followups if item.due_at and item.due_at < now)

    active_jobs = [job for job in job_list if job.archived_at is None]
    average_days_in_stage = 0.0
    if active_jobs:
        total_days = 0.0
        counted_jobs = 0
        for job in active_jobs:
            if job.last_status_changed_at is None:
                continue
            total_days += max((now - job.last_status_changed_at).total_seconds(), 0) / 86400
            counted_jobs += 1
        if counted_jobs:
            average_days_in_stage = round(total_days / counted_jobs, 2)

    total_jobs = len(job_list)
    saved_jobs_count = jobs_by_status.get(TRACKED_JOB_STATUS_SAVED, 0)
    applications_submitted = len(jobs_reached_applied)
    interviews_count = len(jobs_reached_interview)
    offers_count = jobs_by_status.get(TRACKED_JOB_STATUS_OFFER, 0)
    rejections_count = jobs_by_status.get(TRACKED_JOB_STATUS_REJECTED, 0)

    def ratio(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator, 4)

    return JobTrackerMetricsResponse(
        total_jobs=total_jobs,
        saved_jobs_count=saved_jobs_count,
        applications_submitted=applications_submitted,
        interviews_count=interviews_count,
        offers_count=offers_count,
        rejections_count=rejections_count,
        conversion_saved_to_applied=ratio(applications_submitted, max(saved_jobs_count, 1)),
        conversion_applied_to_interview=ratio(interviews_count, applications_submitted),
        conversion_interview_to_offer=ratio(offers_count, interviews_count),
        jobs_by_status=dict(jobs_by_status),
        overdue_followups_count=overdue_followups_count,
        average_days_in_stage=average_days_in_stage,
    )


def build_tracked_jobs_csv(*, jobs: Iterable[TrackedJob]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "company",
            "role",
            "location",
            "site",
            "status",
            "deadline",
            "next_follow_up",
            "applied_at",
            "priority",
            "updated_at",
            "job_url",
            "apply_url",
            "notes_summary",
        ]
    )
    for job in jobs:
        writer.writerow(
            [
                job.company_name,
                job.title,
                job.location or "",
                job.site or "",
                job.status,
                job.deadline_at.isoformat() if job.deadline_at else "",
                job.next_follow_up_at.isoformat() if job.next_follow_up_at else "",
                job.applied_at.isoformat() if job.applied_at else "",
                job.priority,
                job.updated_at.isoformat() if job.updated_at else "",
                job.source_job_url or "",
                job.apply_url or "",
                job.notes_summary or "",
            ]
        )
    return buffer.getvalue()
