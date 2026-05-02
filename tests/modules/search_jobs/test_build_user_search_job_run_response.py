from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from src.modules.search_jobs.use_cases.build_user_search_job_run_response import (
    build_user_search_job_run_response,
)


def test_build_user_search_job_run_response_limits_free_results_and_enriches_tracker_state(
    monkeypatch,
) -> None:
    tracked_job_id = uuid4()
    created_at = datetime(2026, 3, 28, 9, 0, tzinfo=UTC)
    workflow_run = SimpleNamespace(
        id=uuid4(),
        onboarding_session_id=uuid4(),
        user_id="user-1",
        status="completed",
        search_strategy_summary="Focus on remote frontend roles.",
        hard_preferences=["Remote"],
        soft_preferences=["Early stage"],
        source_sites=["linkedin"],
        monitoring_mode=False,
        total_site_results=10,
        total_jobs_found=4,
        total_jobs_returned=4,
        summary_markdown=None,
        jobs=[
            _job_dict("https://example.com/job-1/"),
            _job_dict("https://example.com/job-2"),
            _job_dict("https://example.com/job-3"),
            _job_dict("https://example.com/job-4"),
        ],
        site_results=[],
        notes=[],
        search_model=None,
        unification_model=None,
        error_message=None,
        current_internal_stage="completed",
        current_display_stage="completed",
        current_display_label="Search complete",
        current_display_description="Done",
        progress_percent=100,
        progress_stage_index=6,
        progress_stage_total=6,
        started_at=None,
        finished_at=None,
        last_progress_at=created_at,
        created_at=created_at,
        updated_at=created_at,
    )

    async def fake_get_subscription(self, *, user_id: str):
        assert user_id == "user-1"
        return None

    async def fake_get_access_pass(self, *, user_id: str):
        assert user_id == "user-1"
        return None

    async def fake_list_jobs_for_user(self, *, user_id: str, query):
        assert user_id == "user-1"
        assert query.archived is False
        return [
            SimpleNamespace(
                id=tracked_job_id,
                source_job_url="https://example.com/job-1",
                archived_at=None,
            )
        ]

    monkeypatch.setattr(
        "src.modules.search_jobs.use_cases.build_user_search_job_run_response."
        "BillingSubscriptionsRepository.get_by_user_id",
        fake_get_subscription,
    )
    monkeypatch.setattr(
        "src.modules.search_jobs.use_cases.build_user_search_job_run_response."
        "BillingAccessPassesRepository.get_active_for_user",
        fake_get_access_pass,
    )
    monkeypatch.setattr(
        "src.modules.search_jobs.use_cases.build_user_search_job_run_response."
        "TrackedJobsRepository.list_jobs_for_user",
        fake_list_jobs_for_user,
    )

    response = asyncio.run(
        build_user_search_job_run_response(
            session=object(),
            user_id="user-1",
            workflow_run=workflow_run,
        )
    )

    assert response.billing_plan == "free"
    assert response.viewer_job_limit == 3
    assert response.visible_jobs_count == 3
    assert response.hidden_jobs_count == 1
    assert [job.job_url for job in response.jobs] == [
        "https://example.com/job-1/",
        "https://example.com/job-2",
        "https://example.com/job-3",
    ]
    assert response.jobs[0].is_saved_to_tracker is True
    assert response.jobs[0].tracked_job_id == str(tracked_job_id)
    assert response.jobs[0].site_display_name == "LinkedIn"
    assert response.jobs[0].display_badge_label == "High"


def _job_dict(job_url: str) -> dict[str, object]:
    return {
        "site": "linkedin",
        "job_url": job_url,
        "title": "Frontend Engineer",
        "company_name": "Acme",
        "location": "Remote",
        "salary_text": "$120k",
        "salary_min": 120000,
        "salary_max": 120000,
        "currency": "USD",
        "employment_type": "full-time",
        "published_at": None,
        "description": None,
        "skills": [],
        "apply_url": None,
        "company_url": None,
        "company_about": None,
        "company_contacts": [],
        "why_apply": "Strong product fit.",
        "risks": [],
        "fit_level": "high",
        "source_queries": [],
    }
