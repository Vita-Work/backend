import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from src.extensions.resend import ResendEmailError
from src.modules.auth import routes as auth_routes
from src.modules.auth.schemas import RequestEmailCodeRequest
from starlette.requests import Request


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.deleted_instances: list[object] = []

    async def commit(self) -> None:
        self.commit_calls += 1

    async def delete(self, instance: object) -> None:
        self.deleted_instances.append(instance)


class FakeAuthRepository:
    def __init__(self, *, session: FakeSession) -> None:
        self.session = session

    async def count_recent_challenges(self, *, email: str, since) -> int:
        return 0

    async def get_latest_challenge(self, *, email: str):
        return None

    async def invalidate_active_challenges(self, *, email: str) -> None:
        return None

    def add_challenge(self, **kwargs):
        challenge = SimpleNamespace(**kwargs)
        self.session.challenge = challenge
        return challenge


class FailingResendClient:
    async def send_email(self, **kwargs) -> None:
        raise ResendEmailError("Resend is not configured.")


def test_request_email_code_deletes_challenge_when_email_send_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    request = Request(
        {
            "type": "http",
            "client": ("127.0.0.1", 12345),
            "headers": [(b"user-agent", b"pytest")],
        }
    )

    monkeypatch.setattr(auth_routes, "AuthRepository", FakeAuthRepository)
    monkeypatch.setattr(auth_routes, "ResendClient", lambda: FailingResendClient())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            auth_routes.request_email_code_route(
                RequestEmailCodeRequest(email="debug@example.com"),
                request,
                session,
            )
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Resend is not configured."
    assert session.commit_calls == 2
    assert session.deleted_instances == [session.challenge]
