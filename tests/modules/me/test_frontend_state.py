import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from src.modules.me import frontend_state as frontend_state_module
from src.modules.me.frontend_state import route_for_app_phase


def test_route_for_app_phase_matches_frontend_routes() -> None:
    assert route_for_app_phase("new_user") == "/onboarding"
    assert route_for_app_phase("upload_cv") == "/onboarding"
    assert route_for_app_phase("processing_cv") == "/onboarding/processing"
    assert route_for_app_phase("onboarding_chat") == "/onboarding/chat"
    assert route_for_app_phase("awaiting_confirmation") == "/onboarding/chat"
    assert route_for_app_phase("searching_jobs") == "/searching"
    assert route_for_app_phase("results_ready") == "/results"


def test_build_app_state_snapshot_includes_last_failed_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed_run_id = uuid4()
    failed_run = SimpleNamespace(
        id=failed_run_id,
        status="failed",
        ui_phase="failed",
        ui_label="Extraction failed",
        ui_description="The CV processor hit provider limits. Please try again in a few minutes.",
        finished_at=None,
        updated_at=None,
    )
    failure_event = SimpleNamespace(
        payload={
            "error_code": "provider_quota_exhausted",
            "retryable": True,
        }
    )

    class FakeOnboardingRepository:
        def __init__(self, *, session) -> None:
            _ = session

        async def get_active_for_user(self, *, user_id: str):
            _ = user_id
            return None

        async def get_latest_completed_for_user(self, *, user_id: str):
            _ = user_id
            return None

    class FakeExtractionRepository:
        def __init__(self, *, session) -> None:
            _ = session

        async def get_latest_for_user(self, *, user_id: str):
            _ = user_id
            return failed_run

        async def get_latest_failure_event(self, *, workflow_run_id):
            assert workflow_run_id == failed_run_id
            return failure_event

    class FakeSearchRepository:
        def __init__(self, *, session) -> None:
            _ = session

        async def get_latest_for_user(self, *, user_id: str):
            _ = user_id
            return None

    class FakeTrackerRepository:
        def __init__(self, *, session) -> None:
            _ = session

        async def list_jobs_for_user(self, *, user_id: str, query):
            _ = user_id
            _ = query
            return []

    monkeypatch.setattr(
        frontend_state_module,
        "OnboardingSessionsRepository",
        FakeOnboardingRepository,
    )
    monkeypatch.setattr(
        frontend_state_module,
        "ExtractionWorkflowRunsRepository",
        FakeExtractionRepository,
    )
    monkeypatch.setattr(
        frontend_state_module,
        "SearchJobWorkflowRunsRepository",
        FakeSearchRepository,
    )
    monkeypatch.setattr(
        frontend_state_module,
        "TrackedJobsRepository",
        FakeTrackerRepository,
    )

    snapshot = asyncio.run(
        frontend_state_module.build_app_state_snapshot(
            session=object(),
            user=SimpleNamespace(id="user-1"),
        )
    )

    assert snapshot.phase == "upload_cv"
    assert snapshot.last_failed_extraction is not None
    assert snapshot.last_failed_extraction.workflow_run_id == failed_run_id
    assert snapshot.last_failed_extraction.error_code == "provider_quota_exhausted"
    assert snapshot.last_failed_extraction.retry_available is True
