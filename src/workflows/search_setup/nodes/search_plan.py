from __future__ import annotations

from src.extensions.dspy import get_dspy_search_setup_service
from src.logger import get_logger
from src.workflows.search_setup.state import SearchSetupState

logger = get_logger("workflows.search_setup.search_plan")


async def search_plan_node(state: SearchSetupState) -> dict[str, object]:
    """Generate the search plan from the verified candidate context."""
    log = logger.bind(
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
    )
    log.info("search_plan_started")

    service = get_dspy_search_setup_service()
    result = await service.build_search_plan(
        planning_context=_build_planning_context(state),
        user_profile=state["extracted_profile"],
    )

    log.info(
        "search_plan_completed",
        hard_preferences_count=len(result.hard_preferences),
        soft_preferences_count=len(result.soft_preferences),
    )
    return {
        "search_strategy_summary": result.search_strategy_summary,
        "soft_preferences": result.soft_preferences,
        "hard_preferences": result.hard_preferences,
        "status": "awaiting_confirmation",
    }


def _build_planning_context(state: SearchSetupState) -> str:
    turns = state.get("clarification_turns", [])
    clarification_history = (
        "\n\n".join(f"Q: {turn['question']}\nA: {turn['answer']}" for turn in turns)
        if turns
        else "No clarification history."
    )
    missing_info = "\n".join(f"- {item}" for item in state.get("missing_info", [])) or "- None"
    preference_hints = (
        "\n".join(f"- {item}" for item in state.get("preference_hints", [])) or "- None"
    )
    verification_summary = state.get("verification_summary", "No verification summary.")
    return (
        f"User profile:\n{state['extracted_profile']}\n\n"
        f"Open questions:\n{missing_info}\n\n"
        f"Preference hints:\n{preference_hints}\n\n"
        f"Clarification chat:\n{clarification_history}\n\n"
        f"Verification summary:\n{verification_summary}"
    )
