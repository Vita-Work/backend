import asyncio
from datetime import UTC, date, datetime
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

        async def get_latest_monitoring_run_for_user_in_window(
            self, *, user_id: str, created_at_gte, created_at_lt
        ):
            workflow_repository_state["monitoring_window"] = (
                user_id,
                created_at_gte,
                created_at_lt,
            )
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
    assert "monitoring_window" not in workflow_repository_state
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
    subscription = SimpleNamespace(
        status="active",
        monitoring_last_run_local_date=None,
        plan_code="pro",
    )

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

        async def get_latest_monitoring_run_for_user_in_window(
            self, *, user_id: str, created_at_gte, created_at_lt
        ):
            workflow_repository_state["monitoring_window"] = (
                user_id,
                created_at_gte,
                created_at_lt,
            )
            return None

        def add(self, **kwargs):
            workflow_repository_state["payload"] = kwargs
            return workflow_run

    class FakeRedis:
        async def enqueue_job(self, function: str, *args, **kwargs):
            _ = function, args, kwargs
            return object()

    class FakeAccessPassRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_active_for_user(self, *, user_id: str):
            assert user_id == "user-1"
            return None

    class FakeBillingRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_by_user_id(self, *, user_id: str):
            raise AssertionError("Monitoring checks should lock the subscription row.")

        async def get_by_user_id_for_update(self, *, user_id: str):
            assert user_id == "user-1"
            return subscription

        def add(self, *, user_id: str):
            raise AssertionError("Existing subscription should be reused.")

    async def fake_get_user_timezone(*, session, user_id):
        _ = session, user_id
        return "Asia/Bishkek"

    monkeypatch.setattr(queue_module, "OnboardingSessionsRepository", FakeOnboardingRepository)
    monkeypatch.setattr(queue_module, "SearchJobWorkflowRunsRepository", FakeWorkflowRepository)
    monkeypatch.setattr(queue_module, "BillingSubscriptionsRepository", FakeBillingRepository)
    monkeypatch.setattr(queue_module, "BillingAccessPassesRepository", FakeAccessPassRepository)
    monkeypatch.setattr(queue_module, "_get_user_timezone", fake_get_user_timezone)
    monkeypatch.setattr(
        queue_module,
        "_monitoring_local_date",
        lambda *, timezone, now=None: date(2026, 3, 29),
    )
    monkeypatch.setattr(
        queue_module,
        "_monitoring_day_window_utc",
        lambda *, local_date, timezone: (
            datetime(2026, 3, 28, 18, 0, tzinfo=UTC),
            datetime(2026, 3, 29, 18, 0, tzinfo=UTC),
        ),
    )
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
    assert subscription.monitoring_last_run_local_date == date(2026, 3, 29)
    assert session.commit_calls == 2


def test_queue_search_job_workflow_rejects_monitoring_for_free_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeAsyncSession()

    class FakeBillingRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_by_user_id(self, *, user_id: str):
            return None

        async def get_by_user_id_for_update(self, *, user_id: str):
            assert user_id == "user-1"
            return None

    class FakeAccessPassRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_active_for_user(self, *, user_id: str):
            assert user_id == "user-1"
            return None

    class FakeRedis:
        async def enqueue_job(self, function: str, *args, **kwargs):
            raise AssertionError("Monitoring should be rejected before enqueueing.")

    monkeypatch.setattr(queue_module, "BillingSubscriptionsRepository", FakeBillingRepository)
    monkeypatch.setattr(queue_module, "BillingAccessPassesRepository", FakeAccessPassRepository)

    with pytest.raises(queue_module.SearchJobMonitoringNotAllowedError):
        asyncio.run(
            queue_module.queue_search_job_workflow(
                session=session,
                arq_redis=FakeRedis(),
                user_id="user-1",
                monitoring_mode=True,
            )
        )


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

        async def get_latest_monitoring_run_for_user_in_window(
            self, *, user_id: str, created_at_gte, created_at_lt
        ):
            raise AssertionError("Non-monitoring runs should not query same-day monitoring state.")

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


def test_queue_search_job_workflow_reuses_same_day_monitoring_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeAsyncSession()
    existing_monitoring_run = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        monitoring_mode=True,
        status="completed",
        error_message=None,
    )
    subscription = SimpleNamespace(
        status="active",
        monitoring_last_run_local_date=None,
        plan_code="pro",
    )
    workflow_repository_state: dict[str, object] = {}

    class FakeWorkflowRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_latest_monitoring_run_for_user_in_window(
            self, *, user_id: str, created_at_gte, created_at_lt
        ):
            workflow_repository_state["monitoring_window"] = (
                user_id,
                created_at_gte,
                created_at_lt,
            )
            return existing_monitoring_run

        async def get_latest_active_for_onboarding_session(
            self, *, onboarding_session_id, monitoring_mode
        ):
            raise AssertionError("Same-day monitoring run should short-circuit before onboarding.")

        def add(self, **kwargs):
            raise AssertionError("A second monitoring run must not be created on the same day.")

    class FakeBillingRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_by_user_id_for_update(self, *, user_id: str):
            assert user_id == "user-1"
            return subscription

        async def get_by_user_id(self, *, user_id: str):
            raise AssertionError("Monitoring checks should use the locked subscription lookup.")

    class FakeAccessPassRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_active_for_user(self, *, user_id: str):
            assert user_id == "user-1"
            return None

    class FakeRedis:
        async def enqueue_job(self, function: str, *args, **kwargs):
            raise AssertionError("Existing same-day monitoring runs should not be re-enqueued.")

    async def fake_get_user_timezone(*, session, user_id):
        _ = session, user_id
        return "Asia/Bishkek"

    monkeypatch.setattr(queue_module, "SearchJobWorkflowRunsRepository", FakeWorkflowRepository)
    monkeypatch.setattr(queue_module, "BillingSubscriptionsRepository", FakeBillingRepository)
    monkeypatch.setattr(queue_module, "BillingAccessPassesRepository", FakeAccessPassRepository)
    monkeypatch.setattr(queue_module, "_get_user_timezone", fake_get_user_timezone)
    monkeypatch.setattr(
        queue_module,
        "_monitoring_local_date",
        lambda *, timezone, now=None: date(2026, 3, 29),
    )
    monkeypatch.setattr(
        queue_module,
        "_monitoring_day_window_utc",
        lambda *, local_date, timezone: (
            datetime(2026, 3, 28, 18, 0, tzinfo=UTC),
            datetime(2026, 3, 29, 18, 0, tzinfo=UTC),
        ),
    )

    result = asyncio.run(
        queue_module.queue_search_job_workflow(
            session=session,
            arq_redis=FakeRedis(),
            user_id="user-1",
            monitoring_mode=True,
        )
    )

    assert result is existing_monitoring_run
    assert subscription.monitoring_last_run_local_date == date(2026, 3, 29)
    assert session.flush_calls == 0
    assert session.refresh_calls == []
    assert session.commit_calls == 1
