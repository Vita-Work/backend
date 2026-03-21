from __future__ import annotations

from src.extensions.dspy import get_dspy_search_setup_service
from src.logger import get_logger
from src.workflows.search_setup.state import SearchSetupState

logger = get_logger("workflows.search_setup.verify")


async def verify_node(state: SearchSetupState) -> dict[str, object]:
    """Verify whether the clarified profile is sufficient for search planning."""
    turns = state.get("clarification_turns", [])
    log = logger.bind(
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
    )
    log.info("verification_started")

    service = get_dspy_search_setup_service()
    result = await service.verify_candidate_profile(
        user_profile=state["extracted_profile"],
        missing_info=state.get("missing_info", []),
        clarification_chat=_format_clarification_chat(state.get("clarification_turns", [])),
    )
    retry_count = state.get("verification_retry_count", 0)
    should_retry_clarification = not result.is_verified and retry_count < 1

    log.info(
        "verification_completed",
        is_verified=result.is_verified,
        verification_score=result.verification_score,
        remaining_gaps_count=len(result.remaining_gaps),
        retry_count=retry_count,
    )
    return {
        "verification_score": result.verification_score,
        "verification_summary": result.verification_summary,
        "profile_verified": result.is_verified or not should_retry_clarification,
        "missing_info": result.remaining_gaps,
        "clarification_max_rounds": (
            1 if should_retry_clarification else state.get("clarification_max_rounds")
        ),
        "clarification_cycle_start_index": (
            len(turns)
            if should_retry_clarification
            else state.get("clarification_cycle_start_index", 0)
        ),
        "verification_retry_count": (
            retry_count + 1 if should_retry_clarification else retry_count
        ),
        "status": (
            "planning"
            if (result.is_verified or not should_retry_clarification)
            else "awaiting_clarification"
        ),
    }


def _format_clarification_chat(turns: list[dict[str, str]]) -> str:
    if not turns:
        return "No clarification chat yet."
    return "\n\n".join(f"Q: {turn['question']}\nA: {turn['answer']}" for turn in turns)
