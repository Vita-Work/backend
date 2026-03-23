from __future__ import annotations

import re

from langgraph.types import interrupt

from src.config import get_settings
from src.extensions.gemini import get_gemini_cv_extraction_service
from src.logger import get_logger
from src.workflows.search_setup.state import SearchSetupState

logger = get_logger("workflows.search_setup.clarification")


async def clarification_node(state: SearchSetupState) -> dict[str, object]:
    """Decide the next clarification question or conclude the clarification step."""
    turns = state.get("clarification_turns", [])
    max_rounds = state.get("clarification_max_rounds", get_settings().clarification_max_rounds)
    cycle_start_index = state.get("clarification_cycle_start_index", 0)
    rounds_in_cycle = max(0, len(turns) - cycle_start_index)
    log = logger.bind(
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        clarification_rounds=rounds_in_cycle,
    )
    log.info("clarification_started")

    if rounds_in_cycle >= max_rounds:
        log.info("clarification_max_rounds_reached", max_rounds=max_rounds)
        return {
            "pending_user_prompt": None,
            "pending_user_prompt_type": None,
            "status": "verifying",
        }

    service = get_gemini_cv_extraction_service()
    decision = await service.decide_clarification(
        extracted_profile=state["extracted_profile"],
        missing_info=state.get("missing_info", []),
        preference_hints=state.get("preference_hints", []),
        clarification_turns=turns,
        verification_summary=state.get("verification_summary"),
    )

    question = decision.question.strip() if decision.question else None
    if decision.needs_more_context and not question:
        raise ValueError("Clarification requested more context but did not provide a question.")

    cycle_turns = turns[cycle_start_index:]
    if decision.needs_more_context and _question_was_already_answered(question, cycle_turns):
        log.info("clarification_duplicate_question_detected")
        return {
            "pending_user_prompt": None,
            "pending_user_prompt_type": None,
            "missing_info": decision.missing_info,
            "preference_hints": decision.preference_hints,
            "status": "verifying",
        }

    log.info(
        "clarification_decided",
        needs_more_context=decision.needs_more_context,
        missing_info_count=len(decision.missing_info),
        preference_hints_count=len(decision.preference_hints),
    )
    return {
        "pending_user_prompt": question if decision.needs_more_context else None,
        "pending_user_prompt_type": (
            "clarification_question" if decision.needs_more_context else None
        ),
        "missing_info": decision.missing_info,
        "preference_hints": decision.preference_hints,
        "status": "awaiting_clarification" if decision.needs_more_context else "verifying",
    }


def need_more_context_node(state: SearchSetupState) -> dict[str, object]:
    """Pause the graph for a human answer and append the answer to clarification history."""
    question = (state.get("pending_user_prompt") or "").strip()
    if not question:
        raise ValueError("Clarification question is missing before interrupt.")

    answer = interrupt({"type": "clarification_question", "prompt": question})
    answer_text = str(answer).strip()
    turns = list(state.get("clarification_turns", []))
    turns.append({"question": question, "answer": answer_text})

    logger.info(
        "clarification_answer_received",
        user_id=state["user_id"],
        onboarding_session_id=state["onboarding_session_id"],
        clarification_rounds=max(
            0,
            len(turns) - state.get("clarification_cycle_start_index", 0),
        ),
    )
    return {
        "clarification_turns": turns,
        "pending_user_prompt": None,
        "pending_user_prompt_type": None,
        "confirmation_context": None,
        "status": "verifying",
    }


_QUESTION_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "could",
    "do",
    "for",
    "how",
    "i",
    "in",
    "is",
    "me",
    "my",
    "now",
    "of",
    "on",
    "or",
    "please",
    "should",
    "the",
    "to",
    "we",
    "what",
    "where",
    "which",
    "who",
    "would",
    "you",
    "your",
}


def _question_was_already_answered(question: str, turns: list[dict[str, str]]) -> bool:
    fingerprint = _question_fingerprint(question)
    if not fingerprint:
        return False
    return any(_question_fingerprint(turn.get("question", "")) == fingerprint for turn in turns)


def _question_fingerprint(question: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", question.lower())
        if token not in _QUESTION_STOPWORDS
    ]
    return " ".join(sorted(set(tokens)))
