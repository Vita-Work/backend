from __future__ import annotations

from langgraph.types import interrupt

from src.logger import get_logger
from src.workflows.search_setup.state import SearchSetupState

logger = get_logger("workflows.search_setup.confirm")


def confirm_node(state: SearchSetupState) -> dict[str, object]:
    """Ask the user to confirm the generated search plan."""
    prompt = _build_confirmation_prompt(state)
    answer = interrupt({"type": "confirmation_request", "prompt": prompt})
    normalized_answer = str(answer).strip()
    is_confirmed = _is_affirmative(normalized_answer)

    updates: dict[str, object] = {
        "confirmed": is_confirmed,
        "pending_user_prompt": None,
        "pending_user_prompt_type": None,
        "status": "completed" if is_confirmed else "awaiting_clarification",
    }
    if not is_confirmed:
        turns = list(state.get("clarification_turns", []))
        turns.append(
            {
                "question": "Plan confirmation feedback",
                "answer": normalized_answer,
            }
        )
        updates["clarification_turns"] = turns
        updates["clarification_max_rounds"] = 1
        updates["clarification_cycle_start_index"] = len(turns)
        updates["verification_retry_count"] = 0

    logger.info(
        "confirmation_received",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        confirmed=is_confirmed,
    )
    return updates


def _build_confirmation_prompt(state: SearchSetupState) -> str:
    hard_preferences = (
        "\n".join(f"- {item}" for item in state.get("hard_preferences", [])) or "- None"
    )
    soft_preferences = (
        "\n".join(f"- {item}" for item in state.get("soft_preferences", [])) or "- None"
    )
    return (
        "Please review the proposed search setup.\n\n"
        f"Search strategy summary:\n{state.get('search_strategy_summary', '')}\n\n"
        f"Hard preferences:\n{hard_preferences}\n\n"
        f"Soft preferences:\n{soft_preferences}\n\n"
        "Reply yes to confirm, or no with a short correction."
    )


def _is_affirmative(answer: str) -> bool:
    normalized = answer.strip().lower()
    return normalized in {"yes", "y", "да", "ok", "okay", "confirm", "confirmed"}
