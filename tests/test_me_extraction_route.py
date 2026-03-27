import asyncio
from types import SimpleNamespace

from src.modules.auth.dependencies import AuthContext
from src.modules.me import routes as me_routes


class ExpiringUser:
    def __init__(self, user_id: str) -> None:
        self._id = user_id
        self.expired = False

    @property
    def id(self) -> str:
        if self.expired:
            raise RuntimeError("user object expired after rollback")
        return self._id


class FakeSession:
    def __init__(self, user: ExpiringUser) -> None:
        self.user = user
        self.rollback_calls = 0

    async def rollback(self) -> None:
        self.rollback_calls += 1
        self.user.expired = True


def test_run_my_extraction_route_captures_user_id_before_rollback(monkeypatch) -> None:
    user = ExpiringUser("user-123")
    session = FakeSession(user)
    captured: dict[str, object] = {}

    async def fake_intake_cv_for_extraction(*, upload):
        return "prepared-cv"

    async def fake_queue_cv_extraction_workflow(
        *,
        session,
        arq_redis,
        user_id,
        prepared_cv,
        parent_request_id=None,
    ):
        captured["user_id"] = user_id
        captured["prepared_cv"] = prepared_cv
        captured["parent_request_id"] = parent_request_id
        return "workflow-run"

    monkeypatch.setattr(me_routes, "intake_cv_for_extraction", fake_intake_cv_for_extraction)
    monkeypatch.setattr(
        me_routes, "queue_cv_extraction_workflow", fake_queue_cv_extraction_workflow
    )
    monkeypatch.setattr(
        me_routes,
        "build_extraction_response",
        lambda *, workflow_run: {"workflow_run": workflow_run},
    )

    result = asyncio.run(
        me_routes.run_my_extraction_route(
            request=SimpleNamespace(state=SimpleNamespace(request_id="req-1")),
            file=None,
            context=AuthContext(user=user, session_id="sess", role="user", cookie_name="cookie"),
            session=session,
            arq_redis=object(),
        )
    )

    assert session.rollback_calls == 1
    assert captured["user_id"] == "user-123"
    assert captured["prepared_cv"] == "prepared-cv"
    assert captured["parent_request_id"] == "req-1"
    assert result == {"workflow_run": "workflow-run"}
