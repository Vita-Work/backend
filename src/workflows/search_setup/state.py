from collections.abc import Sequence
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

WorkflowStatus = Literal[
    "ingesting",
    "extracting",
    "clarifying",
    "normalizing",
    "verifying_profile",
    "planning",
    "verifying_plan",
    "awaiting_confirmation",
    "confirmed",
    "queued",
    "completed",
    "failed",
]

ExtractionStrategy = Literal["model_file", "local_text"]


class SearchSetupState(TypedDict):
    """Shared state for the search-setup workflow."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    status: WorkflowStatus

    user_id: str
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
