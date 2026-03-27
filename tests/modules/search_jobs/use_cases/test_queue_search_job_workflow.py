import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from src.modules.search_jobs.use_cases import queue_search_job_workflow as queue_module


class FakeAsyncSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.refresh_calls: list[object] = []
        self.flush_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, instance: object) -> None:
        self.refresh_calls.append(instance)

    async def flush(self) -> None:
        self.flush_calls += 1


def test_queue_search_job_workflow_persists_and_enqueues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeAsyncSession()
    onboarding_session = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        status="completed",
        search_strategy_summary="Focus on remote backend roles in Europe.",
        hard_preferences=["remote"],
        soft_preferences=["product companies"],
    )
    workflow_run = SimpleNamespace(
        id=uuid4(),
        onboarding_session_id=onboarding_session.id,
        user_id="user-1",
        status="queued",
        error_message=None,
    )
    onboarding_repository_state: dict[str, object] = {}
    workflow_repository_state: dict[str, object] = {}
    redis_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    class FakeOnboardingRepository:
        def __init__(self, *, session: object) -> None:
            onboarding_repository_state["session"] = session

        async def get_latest_completed_for_user(self, *, user_id: str):
            onboarding_repository_state["user_id"] = user_id
            return onboarding_session

    class FakeWorkflowRepository:
        def __init__(self, *, session: object) -> None:
            workflow_repository_state["session"] = session

        async def get_latest_active_for_onboarding_session(
            self, *, onboarding_session_id, monitoring_mode
        ):
            workflow_repository_state["latest_onboarding_session_id"] = onboarding_session_id
            workflow_repository_state["latest_monitoring_mode"] = monitoring_mode
            return None

        def add(self, **kwargs):
            workflow_repository_state["payload"] = kwargs
            return workflow_run

    class FakeRedis:
        async def enqueue_job(self, function: str, *args, **kwargs):
            redis_calls.append((function, args, kwargs))
            return object()

    monkeypatch.setattr(queue_module, "OnboardingSessionsRepository", FakeOnboardingRepository)
    monkeypatch.setattr(queue_module, "SearchJobWorkflowRunsRepository", FakeWorkflowRepository)
    monkeypatch.setattr(queue_module, "get_registered_parser_names", lambda: ["alpha", "beta"])

    result = asyncio.run(
        queue_module.queue_search_job_workflow(
            session=session,
            arq_redis=FakeRedis(),
            user_id="user-1",
            parent_request_id="req-2",
        )
    )

    assert result is workflow_run
    assert onboarding_repository_state["user_id"] == "user-1"
    assert workflow_repository_state["latest_onboarding_session_id"] == onboarding_session.id
    assert workflow_repository_state["latest_monitoring_mode"] is False
    assert workflow_repository_state["payload"] == {
        "user_id": "user-1",
        "onboarding_session_id": onboarding_session.id,
        "search_strategy_summary": "Focus on remote backend roles in Europe.",
        "hard_preferences": ["remote"],
        "soft_preferences": ["product companies"],
        "source_sites": ["alpha", "beta"],
        "monitoring_mode": False,
    }
    assert session.flush_calls == 1
    assert session.commit_calls == 1
    assert session.refresh_calls == [workflow_run]
    assert len(redis_calls) == 1
    function, args, kwargs = redis_calls[0]
    assert function == "process_search_job_workflow"
    assert args == (str(workflow_run.id),)
    assert kwargs["_job_id"] == str(workflow_run.id)
    assert kwargs["_parent_request_id"] == "req-2"
    assert kwargs["_user_id"] == "user-1"


def test_queue_search_job_workflow_can_enable_monitoring_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeAsyncSession()
    onboarding_session = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        status="completed",
        search_strategy_summary="Focus on remote backend roles in Europe.",
        hard_preferences=["remote"],
        soft_preferences=["product companies"],
    )
    workflow_run = SimpleNamespace(
        id=uuid4(),
        onboarding_session_id=onboarding_session.id,
        user_id="user-1",
        status="queued",
        error_message=None,
    )
    workflow_repository_state: dict[str, object] = {}

    class FakeOnboardingRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_latest_completed_for_user(self, *, user_id: str):
            assert user_id == "user-1"
            return onboarding_session

    class FakeWorkflowRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_latest_active_for_onboarding_session(
            self, *, onboarding_session_id, monitoring_mode
        ):
            assert onboarding_session_id == onboarding_session.id
            assert monitoring_mode is True
            return None

        def add(self, **kwargs):
            workflow_repository_state["payload"] = kwargs
            return workflow_run

    class FakeRedis:
        async def enqueue_job(self, function: str, *args, **kwargs):
            _ = function, args, kwargs
            return object()

    monkeypatch.setattr(queue_module, "OnboardingSessionsRepository", FakeOnboardingRepository)
    monkeypatch.setattr(queue_module, "SearchJobWorkflowRunsRepository", FakeWorkflowRepository)
    monkeypatch.setattr(queue_module, "get_registered_parser_names", lambda: ["alpha"])

    asyncio.run(
        queue_module.queue_search_job_workflow(
            session=session,
            arq_redis=FakeRedis(),
            user_id="user-1",
            monitoring_mode=True,
        )
    )

    assert workflow_repository_state["payload"]["monitoring_mode"] is True


def test_queue_search_job_workflow_reuses_active_matching_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeAsyncSession()
    onboarding_session = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        status="completed",
        search_strategy_summary="Focus on remote backend roles in Europe.",
        hard_preferences=["remote"],
        soft_preferences=["product companies"],
    )
    existing_run = SimpleNamespace(
        id=uuid4(),
        onboarding_session_id=onboarding_session.id,
        user_id="user-1",
        status="queued",
        error_message=None,
        monitoring_mode=False,
    )
    workflow_repository_state: dict[str, object] = {}
    redis_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    class FakeOnboardingRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_latest_completed_for_user(self, *, user_id: str):
            assert user_id == "user-1"
            return onboarding_session

    class FakeWorkflowRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_latest_active_for_onboarding_session(
            self, *, onboarding_session_id, monitoring_mode
        ):
            workflow_repository_state["onboarding_session_id"] = onboarding_session_id
            workflow_repository_state["monitoring_mode"] = monitoring_mode
            return existing_run

        def add(self, **kwargs):
            raise AssertionError("A new workflow run should not be created when one is active.")

    class FakeRedis:
        async def enqueue_job(self, function: str, *args, **kwargs):
            redis_calls.append((function, args, kwargs))
            return None

    monkeypatch.setattr(queue_module, "OnboardingSessionsRepository", FakeOnboardingRepository)
    monkeypatch.setattr(queue_module, "SearchJobWorkflowRunsRepository", FakeWorkflowRepository)

    result = asyncio.run(
        queue_module.queue_search_job_workflow(
            session=session,
            arq_redis=FakeRedis(),
            user_id="user-1",
        )
    )

    assert result is existing_run
    assert workflow_repository_state == {
        "onboarding_session_id": onboarding_session.id,
        "monitoring_mode": False,
    }
    assert session.flush_calls == 0
    assert session.commit_calls == 0
    assert session.refresh_calls == []
    assert len(redis_calls) == 1
    function, args, kwargs = redis_calls[0]
    assert function == "process_search_job_workflow"
    assert args == (str(existing_run.id),)
    assert kwargs["_job_id"] == str(existing_run.id)
