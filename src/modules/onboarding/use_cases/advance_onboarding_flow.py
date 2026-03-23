from __future__ import annotations

import inspect

from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.modules.onboarding.models import OnboardingSession
from src.modules.onboarding.repository import OnboardingSessionsRepository
from src.workflows.search_setup.runtime import (
    get_search_setup_graph,
    get_search_setup_state,
    invoke_search_setup_graph,
)


class ActiveOnboardingSessionNotFoundError(RuntimeError):
    """Raised when a user has no active onboarding session."""


class OnboardingFlowNotReadyError(RuntimeError):
    """Raised when the onboarding flow cannot proceed from the current state."""


async def advance_onboarding_flow(
    *,
    session: AsyncSession,
    user_id: str,
    answer: str | None = None,
) -> OnboardingSession:
    """Start or resume the onboarding flow for the user's active session."""
    repository = OnboardingSessionsRepository(session=session)
    onboarding_session = await repository.get_active_for_user(user_id=user_id)
    if onboarding_session is None:
        raise ActiveOnboardingSessionNotFoundError("Active onboarding session not found.")

    if not onboarding_session.extracted_profile:
        raise OnboardingFlowNotReadyError(
            "Onboarding flow is not ready because extracted_profile is missing."
        )

    if onboarding_session.status == "completed":
        return onboarding_session

    pending_user_prompt = getattr(onboarding_session, "pending_user_prompt", None)

    if answer is None and pending_user_prompt:
        return onboarding_session

    if answer is not None:
        normalized_answer = answer.strip()
        if not normalized_answer:
            raise OnboardingFlowNotReadyError("Onboarding answer cannot be empty.")
        if not pending_user_prompt:
            raise OnboardingFlowNotReadyError("There is no pending onboarding prompt to answer.")
        graph_input = Command(resume=normalized_answer)
    else:
        graph_input = {
            "messages": [],
            "status": "clarifying",
            "user_id": onboarding_session.user_id,
            "onboarding_session_id": str(onboarding_session.id),
            "cv_object_key": "",
            "cv_object_uri": "",
            "cv_filename": "",
            "cv_content_type": "",
            "cv_extension": "",
            "extraction_strategy": "local_text",
            "extracted_profile": onboarding_session.extracted_profile,
            "missing_info": onboarding_session.missing_info or [],
            "preference_hints": onboarding_session.preference_hints or [],
            "clarification_turns": onboarding_session.clarification_turns or [],
            "clarification_max_rounds": get_settings().clarification_max_rounds,
            "clarification_cycle_start_index": 0,
            "verification_retry_count": 0,
        }

    config = {"configurable": {"thread_id": str(onboarding_session.id)}}
    graph = get_search_setup_graph()
    if inspect.isawaitable(graph):
        await graph
    result = await invoke_search_setup_graph(
        graph_input=graph_input,
        config=config,
        durability="sync",
    )
    snapshot = await get_search_setup_state(config)
    values = snapshot.values or {}

    _apply_graph_state_to_onboarding_session(
        onboarding_session=onboarding_session,
        graph_result=result,
        graph_values=values,
    )
    await session.commit()
    await session.refresh(onboarding_session)
    return onboarding_session


def _apply_graph_state_to_onboarding_session(
    *,
    onboarding_session: OnboardingSession,
    graph_result: dict[str, object],
    graph_values: dict[str, object],
) -> None:
    onboarding_session.clarification_turns = graph_values.get("clarification_turns", [])
    onboarding_session.missing_info = graph_values.get(
        "missing_info",
        onboarding_session.missing_info or [],
    )
    onboarding_session.preference_hints = graph_values.get(
        "preference_hints",
        onboarding_session.preference_hints or [],
    )
    onboarding_session.verification_score = graph_values.get("verification_score")
    onboarding_session.verification_summary = graph_values.get("verification_summary")
    onboarding_session.search_strategy_summary = graph_values.get("search_strategy_summary")
    onboarding_session.hard_preferences = graph_values.get("hard_preferences", [])
    onboarding_session.soft_preferences = graph_values.get("soft_preferences", [])

    interrupts = graph_result.get("__interrupt__", [])
    if interrupts:
        payload = interrupts[0].value if interrupts else {}
        prompt_type = payload.get("type")
        onboarding_session.pending_user_prompt = payload.get("prompt")
        onboarding_session.pending_user_prompt_type = prompt_type
        if prompt_type == "confirmation_request":
            onboarding_session.status = "awaiting_confirmation"
            onboarding_session.current_step = "confirmation"
        else:
            onboarding_session.status = "awaiting_clarification"
            onboarding_session.current_step = "clarification"
        onboarding_session.last_error_message = None
        return

    onboarding_session.pending_user_prompt = None
    onboarding_session.pending_user_prompt_type = None
    onboarding_session.last_error_message = None

    if graph_values.get("confirmed"):
        onboarding_session.status = "completed"
        onboarding_session.current_step = "done"
        return

    onboarding_session.status = graph_values.get("status", onboarding_session.status)
    if onboarding_session.status == "planning":
        onboarding_session.current_step = "planning"
    elif onboarding_session.status == "verifying":
        onboarding_session.current_step = "verification"
