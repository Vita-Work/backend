from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from src.modules.job_tracker.models import TrackedJob, TrackedJobActivity
from src.modules.job_tracker.service import (
    apply_status_transition,
    build_tracked_jobs_csv,
    compute_job_tracker_metrics,
    normalize_job_url,
)


def _build_job(*, status: str, last_status_changed_at: datetime | None = None) -> TrackedJob:
    return TrackedJob(
        id=uuid4(),
        user_id="user-1",
        source_type="manual",
        source_search_job_run_id=None,
        source_job_url="https://example.com/job/1",
        site="manual",
        title="ML Engineer",
        company_name="Vita",
        location="Remote",
        salary_text=None,
        employment_type=None,
        apply_url=None,
        description_snapshot=None,
        skills_snapshot=["python"],
        fit_level=None,
        why_apply_snapshot=None,
        status=status,
        priority="medium",
        deadline_at=None,
        applied_at=None,
        last_status_changed_at=last_status_changed_at,
        next_follow_up_at=None,
        notes_summary="note",
        archived_at=None,
    )


def test_normalize_job_url_trims_and_drops_fragment() -> None:
    assert (
        normalize_job_url("https://Example.com/jobs/123/?a=1#fragment")
        == "https://example.com/jobs/123?a=1"
    )


def test_apply_status_transition_sets_applied_and_archived_timestamps() -> None:
    job = _build_job(status="saved")

    apply_status_transition(tracked_job=job, status="applied")
    assert job.status == "applied"
    assert job.applied_at is not None
    assert job.last_status_changed_at is not None

    apply_status_transition(tracked_job=job, status="archived")
    assert job.status == "archived"
    assert job.archived_at is not None


def test_compute_job_tracker_metrics_counts_funnel_and_followups() -> None:
    now = datetime(2026, 3, 23, 18, 0, tzinfo=UTC)
    saved_job = _build_job(status="saved", last_status_changed_at=now - timedelta(days=1))
    applied_job = _build_job(status="applied", last_status_changed_at=now - timedelta(days=3))
    offer_job = _build_job(status="offer", last_status_changed_at=now - timedelta(days=5))
    offer_job.applied_at = now - timedelta(days=7)

    follow_up = TrackedJobActivity(
        id=uuid4(),
        tracked_job_id=applied_job.id,
        user_id="user-1",
        activity_type="follow_up",
        title="Follow up",
        body=None,
        status_from=None,
        status_to=None,
        due_at=now - timedelta(days=1),
        completed_at=None,
        event_at=now - timedelta(days=2),
        interview_format=None,
        outcome=None,
        details={},
    )
    interview = TrackedJobActivity(
        id=uuid4(),
        tracked_job_id=offer_job.id,
        user_id="user-1",
        activity_type="interview",
        title="Interview",
        body=None,
        status_from=None,
        status_to=None,
        due_at=None,
        completed_at=None,
        event_at=now - timedelta(days=4),
        interview_format="zoom",
        outcome=None,
        details={},
    )

    metrics = compute_job_tracker_metrics(
        jobs=[saved_job, applied_job, offer_job],
        activities=[follow_up, interview],
        now=now,
    )

    assert metrics.total_jobs == 3
    assert metrics.saved_jobs_count == 1
    assert metrics.applications_submitted == 2
    assert metrics.interviews_count == 1
    assert metrics.offers_count == 1
    assert metrics.overdue_followups_count == 1
    assert metrics.jobs_by_status["saved"] == 1
    assert metrics.jobs_by_status["offer"] == 1
    assert metrics.average_days_in_stage > 0


def test_build_tracked_jobs_csv_contains_expected_columns() -> None:
    job = _build_job(status="saved")
    csv_payload = build_tracked_jobs_csv(jobs=[job])

    assert "company,role,location,site,status" in csv_payload
    assert "Vita,ML Engineer,Remote,manual,saved" in csv_payload
