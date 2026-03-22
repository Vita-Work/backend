from types import SimpleNamespace
from uuid import uuid4

import pytest
from src.workflows.search_job.context import build_search_job_context


def test_build_search_job_context_uses_search_setup_outputs() -> None:
    onboarding_session = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        search_strategy_summary="Focus on academic research roles.",
        hard_preferences=["remote", "Europe"],
        soft_preferences=["research institutes"],
    )

    context = build_search_job_context(onboarding_session=onboarding_session)

    assert context.user_id == "user-1"
    assert context.search_strategy_summary == "Focus on academic research roles."
    assert context.hard_preferences == ["remote", "Europe"]
    assert context.soft_preferences == ["research institutes"]


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_message"),
    [
        ("search_strategy_summary", None, "search_strategy_summary"),
    ],
)
def test_build_search_job_context_requires_completed_search_setup_outputs(
    field_name: str,
    field_value: str | None,
    expected_message: str,
) -> None:
    onboarding_session = SimpleNamespace(
        id=uuid4(),
        user_id="user-1",
        search_strategy_summary="Focus on academic research roles.",
        hard_preferences=[],
        soft_preferences=[],
    )
    setattr(onboarding_session, field_name, field_value)

    with pytest.raises(ValueError, match=expected_message):
        build_search_job_context(onboarding_session=onboarding_session)
