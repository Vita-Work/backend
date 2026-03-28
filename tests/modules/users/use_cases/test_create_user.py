import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from src.modules.users.use_cases import create_user as create_user_module


class FakeAsyncSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0
        self.refresh_calls: list[object] = []

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, instance: object) -> None:
        self.refresh_calls.append(instance)

    async def rollback(self) -> None:
        self.rollback_calls += 1


def test_create_user_normalizes_fields_and_persists(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeAsyncSession()
    repository_state: dict[str, object] = {}

    class FakeUsersRepository:
        def __init__(self, *, session: object) -> None:
            repository_state["session"] = session

        async def get_by_email(self, *, email: str):
            repository_state["lookup_email"] = email
            return None

        def add(
            self,
            *,
            email: str | None,
            full_name: str | None,
            timezone: str,
            locale: str | None,
            role: str,
            password_hash: str | None,
            email_verified_at,
            status: str,
        ):
            repository_state["added_payload"] = {
                "email": email,
                "full_name": full_name,
                "timezone": timezone,
                "locale": locale,
                "role": role,
                "password_hash": password_hash,
                "email_verified_at": email_verified_at,
                "status": status,
            }
            return SimpleNamespace(
                id=uuid4(),
                email=email,
                full_name=full_name,
                timezone=timezone,
                locale=locale,
                status="active",
            )

    monkeypatch.setattr(create_user_module, "UsersRepository", FakeUsersRepository)

    user = asyncio.run(
        create_user_module.create_user(
            session=session,
            email="  TEST@Example.COM ",
            full_name="  Test User  ",
            timezone="   ",
            locale="  ru  ",
        )
    )

    assert repository_state["session"] is session
    assert repository_state["lookup_email"] == "test@example.com"
    assert repository_state["added_payload"] == {
        "email": "test@example.com",
        "full_name": "Test User",
        "timezone": "UTC",
        "locale": "ru",
        "role": "user",
        "password_hash": None,
        "email_verified_at": None,
        "status": "active",
    }
    assert session.commit_calls == 1
    assert session.refresh_calls == [user]
    assert user.email == "test@example.com"
    assert user.full_name == "Test User"
    assert user.timezone == "UTC"
    assert user.locale == "ru"


def test_create_user_raises_for_duplicate_email(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeAsyncSession()
    existing_user = SimpleNamespace(id=uuid4())

    class FakeUsersRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_by_email(self, *, email: str):
            return existing_user

        def add(
            self,
            *,
            email: str | None,
            full_name: str | None,
            timezone: str,
            locale: str | None,
            role: str,
            password_hash: str | None,
            email_verified_at,
            status: str,
        ):
            raise AssertionError("add should not be called when email already exists")

    monkeypatch.setattr(create_user_module, "UsersRepository", FakeUsersRepository)

    with pytest.raises(create_user_module.UserEmailAlreadyExistsError):
        asyncio.run(
            create_user_module.create_user(
                session=session,
                email="existing@example.com",
                full_name="Existing User",
                timezone="Asia/Bishkek",
                locale=None,
            )
        )

    assert session.commit_calls == 0
    assert session.refresh_calls == []


def test_create_user_maps_integrity_error_to_duplicate_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeAsyncSession()
    new_user = SimpleNamespace(id=uuid4())

    class DuplicateEmailError(Exception):
        sqlstate = "23505"

        def __str__(self) -> str:
            return 'duplicate key value violates unique constraint "uq_users_email"'

    class FakeUsersRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_by_email(self, *, email: str):
            return None

        def add(
            self,
            *,
            email: str | None,
            full_name: str | None,
            timezone: str,
            locale: str | None,
            role: str,
            password_hash: str | None,
            email_verified_at,
            status: str,
        ):
            return new_user

    async def failing_commit() -> None:
        session.commit_calls += 1
        raise IntegrityError("INSERT INTO users", {}, DuplicateEmailError())

    monkeypatch.setattr(create_user_module, "UsersRepository", FakeUsersRepository)
    session.commit = failing_commit

    with pytest.raises(create_user_module.UserEmailAlreadyExistsError):
        asyncio.run(
            create_user_module.create_user(
                session=session,
                email="dupe@example.com",
                full_name="Dupe User",
                timezone="UTC",
                locale=None,
            )
        )

    assert session.commit_calls == 1
    assert session.rollback_calls == 1
    assert session.refresh_calls == []
