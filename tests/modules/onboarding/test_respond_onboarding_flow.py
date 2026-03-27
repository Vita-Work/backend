from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.modules.onboarding.use_cases.respond_onboarding_flow import respond_onboarding_flow


def test_respond_onboarding_flow_keeps_non_terminal_sessions_local(monkeypatch) -> None:
    captured: dict[str, object] = {"queue_calls": 0}

    async def fake_advance_onboarding_flow(*, session, user_id: str, answer: str):
        assert user_id == "user-1"
        assert answer == "remote only"
        return SimpleNamespace(status="awaiting_clarification")

    async def fake_queue_search_job_workflow(*, session, arq_redis, user_id: str) -> None:
        captured["queue_calls"] = int(captured["queue_calls"]) + 1

    monkeypatch.setattr(
        "src.modules.onboarding.use_cases.respond_onboarding_flow.advance_onboarding_flow",
        fake_advance_onboarding_flow,
    )
    monkeypatch.setattr(
        "src.modules.onboarding.use_cases.respond_onboarding_flow.queue_search_job_workflow",
        fake_queue_search_job_workflow,
    )

    result = asyncio.run(
        respond_onboarding_flow(
            session=object(),
            arq_redis=object(),
            user_id="user-1",
            answer="remote only",
        )
    )

    assert result.status == "awaiting_clarification"
    assert captured["queue_calls"] == 0


def test_respond_onboarding_flow_queues_search_when_onboarding_finishes(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_advance_onboarding_flow(*, session, user_id: str, answer: str):
        return SimpleNamespace(status="completed")

    async def fake_queue_search_job_workflow(*, session, arq_redis, user_id: str) -> None:
        captured["user_id"] = user_id

    monkeypatch.setattr(
        "src.modules.onboarding.use_cases.respond_onboarding_flow.advance_onboarding_flow",
        fake_advance_onboarding_flow,
    )
    monkeypatch.setattr(
        "src.modules.onboarding.use_cases.respond_onboarding_flow.queue_search_job_workflow",
        fake_queue_search_job_workflow,
    )

    result = asyncio.run(
        respond_onboarding_flow(
            session=object(),
            arq_redis=object(),
            user_id="user-1",
            answer="remote only",
        )
    )

    assert result.status == "completed"
    assert captured["user_id"] == "user-1"
