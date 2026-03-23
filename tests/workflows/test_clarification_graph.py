import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from src.workflows.search_setup.graph import build_search_setup_graph
from src.workflows.search_setup.nodes import (
    clarification as clarification_module,
)
from src.workflows.search_setup.nodes import (
    search_plan as search_plan_module,
)
from src.workflows.search_setup.nodes import (
    verify as verify_module,
)


def test_clarification_graph_interrupts_and_resumes(monkeypatch: pytest.MonkeyPatch) -> None:
    decisions = iter(
        [
            SimpleNamespace(
                needs_more_context=True,
                question="What location are you targeting?",
                missing_info=["salary expectations"],
                preference_hints=["remote"],
            ),
            SimpleNamespace(
                needs_more_context=False,
                question=None,
                missing_info=[],
                preference_hints=["remote", "europe"],
            ),
        ]
    )

    class FakeService:
        model = "gemini-test"

        async def decide_clarification(self, **kwargs):
            return next(decisions)

    monkeypatch.setattr(
        clarification_module,
        "get_gemini_cv_extraction_service",
        lambda: FakeService(),
    )

    class FakeDspyService:
        async def verify_candidate_profile(self, **kwargs):
            return SimpleNamespace(
                verification_score=0.91,
                is_verified=True,
                verification_summary="The candidate context is sufficient for planning.",
                remaining_gaps=[],
            )

        async def build_search_plan(self, **kwargs):
            return SimpleNamespace(
                search_strategy_summary="Focus on remote backend roles in Europe.",
                hard_preferences=["remote", "Europe"],
                soft_preferences=["product companies"],
            )

    monkeypatch.setattr(
        verify_module,
        "get_dspy_search_setup_service",
        lambda: FakeDspyService(),
    )
    monkeypatch.setattr(
        search_plan_module,
        "get_dspy_search_setup_service",
        lambda: FakeDspyService(),
    )

    graph = build_search_setup_graph(checkpointer=InMemorySaver())
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "user_id": "user-1",
        "onboarding_session_id": thread_id,
        "extracted_profile": "Senior backend engineer",
        "missing_info": ["location"],
        "preference_hints": ["remote"],
        "clarification_turns": [],
    }

    first_result = asyncio.run(graph.ainvoke(initial_state, config))
    assert first_result["pending_user_prompt"] == "What location are you targeting?"
    assert "__interrupt__" in first_result
    assert first_result["__interrupt__"][0].value["prompt"] == "What location are you targeting?"

    second_result = asyncio.run(graph.ainvoke(Command(resume="Remote within EU"), config))
    assert second_result["status"] == "awaiting_confirmation"
    assert second_result["clarification_turns"] == [
        {
            "question": "What location are you targeting?",
            "answer": "Remote within EU",
        }
    ]
    assert "__interrupt__" in second_result
    assert second_result["__interrupt__"][0].value["type"] == "confirmation_request"


def test_confirmation_rejection_reopens_one_corrective_clarification_round(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decisions = iter(
        [
            SimpleNamespace(
                needs_more_context=False,
                question=None,
                missing_info=[],
                preference_hints=["academic"],
            ),
            SimpleNamespace(
                needs_more_context=True,
                question="Should we exclude industry roles entirely?",
                missing_info=["industry preference"],
                preference_hints=["academic"],
            ),
        ]
    )

    class FakeService:
        model = "gemini-test"

        async def decide_clarification(self, **kwargs):
            return next(decisions)

    monkeypatch.setattr(
        clarification_module,
        "get_gemini_cv_extraction_service",
        lambda: FakeService(),
    )

    class FakeDspyService:
        async def verify_candidate_profile(self, **kwargs):
            return SimpleNamespace(
                verification_score=0.91,
                is_verified=True,
                verification_summary="Profile is sufficient for planning.",
                remaining_gaps=[],
            )

        async def build_search_plan(self, **kwargs):
            return SimpleNamespace(
                search_strategy_summary="Focus on academic roles.",
                hard_preferences=["academic"],
                soft_preferences=["research"],
            )

    monkeypatch.setattr(
        verify_module,
        "get_dspy_search_setup_service",
        lambda: FakeDspyService(),
    )
    monkeypatch.setattr(
        search_plan_module,
        "get_dspy_search_setup_service",
        lambda: FakeDspyService(),
    )

    graph = build_search_setup_graph(checkpointer=InMemorySaver())
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "user_id": "user-1",
        "onboarding_session_id": thread_id,
        "extracted_profile": "Research candidate",
        "missing_info": [],
        "preference_hints": ["academic"],
        "clarification_turns": [],
    }

    first_result = asyncio.run(graph.ainvoke(initial_state, config))
    assert first_result["status"] == "awaiting_confirmation"
    assert first_result["__interrupt__"][0].value["type"] == "confirmation_request"

    second_result = asyncio.run(
        graph.ainvoke(
            Command(resume="no, please exclude industry roles entirely"),
            config,
        )
    )

    assert second_result["status"] == "awaiting_clarification"
    assert second_result["pending_user_prompt"] == "Should we exclude industry roles entirely?"
    assert second_result["clarification_cycle_start_index"] == 1
    assert second_result["clarification_max_rounds"] == 1
    assert second_result["clarification_turns"][-1] == {
        "question": "Plan confirmation feedback",
        "answer": "no, please exclude industry roles entirely",
    }


def test_clarification_node_skips_duplicate_question_in_current_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_decide_clarification(**kwargs):
        return SimpleNamespace(
            needs_more_context=True,
            question="What seniority are you targeting now?",
            missing_info=["seniority"],
            preference_hints=["engineering"],
        )

    monkeypatch.setattr(
        clarification_module,
        "get_gemini_cv_extraction_service",
        lambda: SimpleNamespace(decide_clarification=fake_decide_clarification),
    )

    result = asyncio.run(
        clarification_module.clarification_node(
            {
                "user_id": "user-1",
                "onboarding_session_id": "session-1",
                "extracted_profile": "Senior engineer",
                "missing_info": ["seniority"],
                "preference_hints": [],
                "clarification_turns": [
                    {
                        "question": "What seniority are you targeting?",
                        "answer": "Junior",
                    }
                ],
                "clarification_cycle_start_index": 0,
                "clarification_max_rounds": 2,
            }
        )
    )

    assert result["pending_user_prompt"] is None
    assert result["status"] == "verifying"


def test_conflict_confirmation_moves_to_planning_without_reopening_clarification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decisions = iter(
        [
            SimpleNamespace(
                needs_more_context=True,
                question="What seniority are you targeting now?",
                missing_info=["seniority"],
                preference_hints=["engineering"],
            )
        ]
    )

    class FakeGeminiService:
        model = "gemini-test"

        async def decide_clarification(self, **kwargs):
            return next(decisions)

    monkeypatch.setattr(
        clarification_module,
        "get_gemini_cv_extraction_service",
        lambda: FakeGeminiService(),
    )

    class FakeDspyService:
        async def verify_candidate_profile(self, **kwargs):
            chat = kwargs["clarification_chat"]
            if "Q: What seniority are you targeting?" not in chat:
                return SimpleNamespace(
                    verification_score=0.41,
                    is_verified=False,
                    verification_summary="Seniority is unclear.",
                    remaining_gaps=["seniority"],
                )
            return SimpleNamespace(
                verification_score=0.44,
                is_verified=False,
                verification_summary="Seniority still conflicts with the CV.",
                remaining_gaps=["seniority"],
            )

        async def build_search_plan(self, **kwargs):
            planning_context = kwargs["planning_context"]
            assert "Conflict resolution feedback" in planning_context
            return SimpleNamespace(
                search_strategy_summary="Target junior backend roles.",
                hard_preferences=["junior backend"],
                soft_preferences=["mentorship"],
            )

    monkeypatch.setattr(
        verify_module,
        "get_dspy_search_setup_service",
        lambda: FakeDspyService(),
    )
    monkeypatch.setattr(
        search_plan_module,
        "get_dspy_search_setup_service",
        lambda: FakeDspyService(),
    )

    graph = build_search_setup_graph(checkpointer=InMemorySaver())
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "user_id": "user-1",
        "onboarding_session_id": thread_id,
        "extracted_profile": "Senior backend engineer",
        "missing_info": ["seniority"],
        "preference_hints": ["engineering"],
        "clarification_turns": [
            {"question": "What seniority are you targeting?", "answer": "Junior"}
        ],
        "clarification_cycle_start_index": 0,
        "clarification_max_rounds": 1,
        "verification_retry_count": 1,
    }

    first_result = asyncio.run(graph.ainvoke(initial_state, config))
    assert first_result["status"] == "awaiting_confirmation"
    assert first_result["__interrupt__"][0].value["type"] == "confirmation_request"
    assert (
        "latest explicit answer will be treated as the source of truth"
        in first_result["__interrupt__"][0].value["prompt"]
    )

    second_result = asyncio.run(graph.ainvoke(Command(resume="No, final answer: junior"), config))
    assert second_result["status"] == "awaiting_confirmation"
    assert second_result["confirmation_context"] == "plan_confirmation"
    assert second_result["hard_preferences"] == ["junior backend"]
    assert second_result["clarification_turns"][-1] == {
        "question": "Conflict resolution feedback",
        "answer": "No, final answer: junior",
    }
