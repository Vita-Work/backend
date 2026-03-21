import asyncio
from types import SimpleNamespace

import pytest
from src.workflows.search_setup.nodes import verify as verify_module


def test_verify_node_requests_one_corrective_round(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeService:
        async def verify_candidate_profile(self, **kwargs):
            return SimpleNamespace(
                verification_score=0.42,
                is_verified=False,
                verification_summary="Location preference is still unclear.",
                remaining_gaps=["location preference"],
            )

    monkeypatch.setattr(verify_module, "get_dspy_search_setup_service", lambda: FakeService())

    result = asyncio.run(
        verify_module.verify_node(
            {
                "user_id": "user-1",
                "onboarding_session_id": "session-1",
                "extracted_profile": "Backend engineer",
                "missing_info": ["location"],
                "preference_hints": [],
                "clarification_turns": [],
                "verification_retry_count": 0,
            }
        )
    )

    assert result["profile_verified"] is False
    assert result["clarification_max_rounds"] == 1
    assert result["clarification_cycle_start_index"] == 0
    assert result["verification_retry_count"] == 1
    assert result["status"] == "awaiting_clarification"


def test_verify_node_proceeds_after_corrective_round_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeService:
        async def verify_candidate_profile(self, **kwargs):
            return SimpleNamespace(
                verification_score=0.48,
                is_verified=False,
                verification_summary="Some ambiguity remains, but proceed to planning.",
                remaining_gaps=["salary expectations"],
            )

    monkeypatch.setattr(verify_module, "get_dspy_search_setup_service", lambda: FakeService())

    result = asyncio.run(
        verify_module.verify_node(
            {
                "user_id": "user-1",
                "onboarding_session_id": "session-1",
                "extracted_profile": "Backend engineer",
                "missing_info": ["salary"],
                "preference_hints": [],
                "clarification_turns": [{"question": "Where?", "answer": "Remote"}],
                "verification_retry_count": 1,
            }
        )
    )

    assert result["profile_verified"] is True
    assert result["status"] == "planning"
    assert result["missing_info"] == ["salary expectations"]
    assert result["clarification_cycle_start_index"] == 0
