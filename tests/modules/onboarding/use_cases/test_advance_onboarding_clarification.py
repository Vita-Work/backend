import asyncio
from types import SimpleNamespace
from uuid import uuid4

from src.modules.onboarding.use_cases import advance_onboarding_flow as flow_module


class FakeAsyncSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.refresh_calls: list[object] = []

    async def commit(self) -> None:
        self.commit_calls += 1

    async def refresh(self, instance: object) -> None:
        self.refresh_calls.append(instance)


def test_advance_onboarding_flow_starts_and_sets_pending_question(monkeypatch) -> None:
    session = FakeAsyncSession()
    onboarding_session = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        status="clarifying",
        current_step="clarification",
        extracted_profile="profile",
        missing_info=["location"],
        preference_hints=["remote"],
        clarification_turns=[],
        pending_user_prompt=None,
        pending_user_prompt_type=None,
        last_error_message=None,
    )

    class FakeRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_active_for_user(self, *, user_id: str):
            assert user_id == "user-1"
            return onboarding_session

    class FakeGraph:
        async def ainvoke(self, graph_input, config, **kwargs):
            assert graph_input["user_id"] == "user-1"
            assert graph_input["onboarding_session_id"] == str(onboarding_session.id)
            assert config["configurable"]["thread_id"] == str(onboarding_session.id)
            return {
                "__interrupt__": [
                    SimpleNamespace(
                        value={
                            "type": "clarification_question",
                            "prompt": "What location are you targeting?",
                        }
                    )
                ]
            }

        async def aget_state(self, config):
            assert config["configurable"]["thread_id"] == str(onboarding_session.id)
            return SimpleNamespace(
                values={
                    "clarification_turns": [],
                    "missing_info": ["salary expectations"],
                    "preference_hints": ["remote"],
                }
            )

    monkeypatch.setattr(flow_module, "OnboardingSessionsRepository", FakeRepository)

    async def fake_get_graph():
        return FakeGraph()

    monkeypatch.setattr(
        flow_module,
        "get_search_setup_graph",
        fake_get_graph,
    )

    result = asyncio.run(
        flow_module.advance_onboarding_flow(
            session=session,
            user_id="user-1",
        )
    )

    assert result is onboarding_session
    assert onboarding_session.status == "awaiting_clarification"
    assert onboarding_session.current_step == "clarification"
    assert onboarding_session.pending_user_prompt == "What location are you targeting?"
    assert onboarding_session.pending_user_prompt_type == "clarification_question"
    assert onboarding_session.missing_info == ["salary expectations"]
    assert onboarding_session.preference_hints == ["remote"]
    assert onboarding_session.clarification_turns == []
    assert session.commit_calls == 1
    assert session.refresh_calls == [onboarding_session]


def test_advance_onboarding_flow_resumes_and_completes(monkeypatch) -> None:
    session = FakeAsyncSession()
    onboarding_session = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        status="awaiting_clarification",
        current_step="clarification",
        extracted_profile="profile",
        missing_info=["location"],
        preference_hints=["remote"],
        clarification_turns=[],
        pending_user_prompt="What location are you targeting?",
        pending_user_prompt_type="clarification_question",
        last_error_message=None,
    )

    class FakeRepository:
        def __init__(self, *, session: object) -> None:
            self.session = session

        async def get_active_for_user(self, *, user_id: str):
            assert user_id == "user-1"
            return onboarding_session

    class FakeGraph:
        async def ainvoke(self, graph_input, config, **kwargs):
            assert isinstance(graph_input, flow_module.Command)
            assert graph_input.resume == "Remote within EU"
            assert config["configurable"]["thread_id"] == str(onboarding_session.id)
            return {
                "status": "completed",
                "confirmed": True,
            }

        async def aget_state(self, config):
            assert config["configurable"]["thread_id"] == str(onboarding_session.id)
            return SimpleNamespace(
                values={
                    "clarification_turns": [
                        {
                            "question": "What location are you targeting?",
                            "answer": "Remote within EU",
                        }
                    ],
                    "missing_info": [],
                    "preference_hints": ["remote", "europe"],
                    "verification_score": 0.92,
                    "verification_summary": "Context is sufficient.",
                    "search_strategy_summary": "Target remote backend roles in Europe.",
                    "hard_preferences": ["remote", "Europe"],
                    "soft_preferences": ["product companies"],
                    "status": "completed",
                    "confirmed": True,
                }
            )

    monkeypatch.setattr(flow_module, "OnboardingSessionsRepository", FakeRepository)

    async def fake_get_graph():
        return FakeGraph()

    monkeypatch.setattr(
        flow_module,
        "get_search_setup_graph",
        fake_get_graph,
    )

    result = asyncio.run(
        flow_module.advance_onboarding_flow(
            session=session,
            user_id="user-1",
            answer="Remote within EU",
        )
    )

    assert result is onboarding_session
    assert onboarding_session.status == "completed"
    assert onboarding_session.current_step == "done"
    assert onboarding_session.pending_user_prompt is None
    assert onboarding_session.clarification_turns == [
        {
            "question": "What location are you targeting?",
            "answer": "Remote within EU",
        }
    ]
    assert onboarding_session.missing_info == []
    assert onboarding_session.preference_hints == ["remote", "europe"]
    assert onboarding_session.verification_score == 0.92
    assert onboarding_session.verification_summary == "Context is sufficient."
    assert onboarding_session.search_strategy_summary == "Target remote backend roles in Europe."
    assert onboarding_session.hard_preferences == ["remote", "Europe"]
    assert onboarding_session.soft_preferences == ["product companies"]
    assert session.commit_calls == 1
    assert session.refresh_calls == [onboarding_session]
