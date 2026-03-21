import asyncio
from types import SimpleNamespace
from uuid import uuid4

from src.modules.onboarding.use_cases import restart_onboarding_session as restart_module


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


def test_restart_onboarding_session_supersedes_existing_active_session(monkeypatch) -> None:
    session = FakeAsyncSession()
    previous_session = SimpleNamespace(
        id=uuid4(),
        status="awaiting_clarification",
        superseded_by_session_id=None,
    )
    new_session = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        status="draft",
        current_step="extraction",
    )
    repository_state: dict[str, object] = {}

    class FakeRepository:
        def __init__(self, *, session: object) -> None:
            repository_state["session"] = session

        async def get_active_for_user(self, *, user_id: str):
            repository_state["active_user_id"] = user_id
            return previous_session

        def add(self, **kwargs):
            repository_state["payload"] = kwargs
            return new_session

    monkeypatch.setattr(restart_module, "OnboardingSessionsRepository", FakeRepository)

    result = asyncio.run(
        restart_module.restart_onboarding_session(
            session=session,
            user_id="user-1",
        )
    )

    assert result is new_session
    assert repository_state["session"] is session
    assert repository_state["active_user_id"] == "user-1"
    assert repository_state["payload"] == {
        "user_id": "user-1",
        "status": "draft",
        "current_step": "extraction",
    }
    assert previous_session.status == "superseded"
    assert previous_session.superseded_by_session_id == new_session.id
    assert session.flush_calls == 2
    assert session.commit_calls == 1
    assert session.refresh_calls == [new_session]
