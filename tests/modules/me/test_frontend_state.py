from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from src.modules.me import frontend_state as frontend_state_module


def test_build_onboarding_thread_projects_messages_for_chat_ui() -> None:
    onboarding_session = SimpleNamespace(
        id=uuid4(),
        created_at=None,
        updated_at=None,
        extracted_profile="profile",
        status="awaiting_confirmation",
        clarification_turns=[
            {"question": "What salary range are you targeting?", "answer": "$4k+"},
            {"question": "Plan confirmation feedback", "answer": "No, prefer remote only."},
        ],
        pending_user_prompt="Please confirm the final plan with Yes or No.",
        pending_user_prompt_type="confirmation_request",
    )

    thread = frontend_state_module.build_onboarding_thread(
        onboarding_session=onboarding_session,
        search_job_workflow_run_id=uuid4(),
    )

    assert thread.conversation_status == "awaiting_confirmation"
    assert thread.input_mode == "confirmation"
    assert thread.confirmation_mode == "yes_no_with_optional_reason"
    assert [message.message_type for message in thread.messages] == [
        "status_note",
        "clarification_question",
        "user_answer",
        "confirmation_answer",
        "confirmation_request",
    ]


def test_build_app_state_snapshot_returns_new_user_for_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeOnboardingRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_active_for_user(self, *, user_id: str):
            assert user_id == "user-1"
            return None

        async def get_latest_completed_for_user(self, *, user_id: str):
            assert user_id == "user-1"
            return None

    class FakeExtractionRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_latest_for_user(self, *, user_id: str):
            assert user_id == "user-1"
            return None

    class FakeSearchRepository(FakeExtractionRepository):
        pass

    class FakeTrackerRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def list_jobs_for_user(self, *, user_id: str, query):
            assert user_id == "user-1"
            assert query.archived is False
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

    assert snapshot.phase == "new_user"
    assert snapshot.next_route == "/auth/welcome"
    assert snapshot.is_new_user is True
    assert snapshot.has_search_results is False


def test_build_app_state_snapshot_returns_results_ready_when_jobs_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed_session = SimpleNamespace(id=uuid4())
    search_run = SimpleNamespace(id=uuid4(), status="completed", jobs=[{"title": "ML Engineer"}])

    class FakeOnboardingRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_active_for_user(self, *, user_id: str):
            return None

        async def get_latest_completed_for_user(self, *, user_id: str):
            return completed_session

    class FakeExtractionRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_latest_for_user(self, *, user_id: str):
            return None

    class FakeSearchRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_latest_for_user(self, *, user_id: str):
            return search_run

    class FakeTrackerRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def list_jobs_for_user(self, *, user_id: str, query):
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

    assert snapshot.phase == "results_ready"
    assert snapshot.next_route == "/jobs"
    assert snapshot.has_completed_onboarding is True
    assert snapshot.has_search_results is True
    assert snapshot.search_job_workflow_run_id == search_run.id
