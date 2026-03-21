from collections.abc import Sequence
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

ExtractionStrategy = Literal["model_file", "local_text"]
PromptType = Literal["clarification_question", "confirmation_request"]
WorkflowStatus = Literal[
    "ingesting",
    "extracting",
    "clarifying",
    "awaiting_clarification",
    "verifying",
    "planning",
    "awaiting_confirmation",
    "completed",
    "failed",
]


class ClarificationTurn(TypedDict):
    """Single clarification exchange."""

    question: str
    answer: str


class SearchSetupState(TypedDict):
    """Unified state for the full search-setup onboarding workflow."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    status: WorkflowStatus

    user_id: str
    onboarding_session_id: str

    cv_object_key: str
    cv_object_uri: str
    cv_filename: str
    cv_content_type: str
    cv_extension: str
    extraction_strategy: ExtractionStrategy

    cv_inline_text: NotRequired[str]

    extracted_profile: NotRequired[str]
    missing_info: NotRequired[list[str]]
    preference_hints: NotRequired[list[str]]
    extraction_model: NotRequired[str]

    clarification_turns: NotRequired[list[ClarificationTurn]]
    clarification_max_rounds: NotRequired[int]
    clarification_cycle_start_index: NotRequired[int]
    pending_user_prompt: NotRequired[str | None]
    pending_user_prompt_type: NotRequired[PromptType | None]

    verification_score: NotRequired[float]
    verification_summary: NotRequired[str]
    profile_verified: NotRequired[bool]
    verification_retry_count: NotRequired[int]

    search_strategy_summary: NotRequired[str]
    soft_preferences: NotRequired[list[str]]
    hard_preferences: NotRequired[list[str]]

    confirmed: NotRequired[bool]
