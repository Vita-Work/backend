import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from src.modules.users.use_cases import get_user as get_user_module


def test_get_user_returns_repository_result(monkeypatch: pytest.MonkeyPatch) -> None:
    session = object()
    user_id = uuid4()
    expected_user = SimpleNamespace(id=user_id, email="user@example.com")
    repository_state: dict[str, object] = {}

    class FakeUsersRepository:
        def __init__(self, *, session: object) -> None:
            repository_state["session"] = session

        async def get_by_id(self, *, user_id):
            repository_state["user_id"] = user_id
            return expected_user

    monkeypatch.setattr(get_user_module, "UsersRepository", FakeUsersRepository)

    result = asyncio.run(get_user_module.get_user(session=session, user_id=user_id))

    assert repository_state == {
        "session": session,
        "user_id": user_id,
    }
    assert result is expected_user
