from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OnboardingSessionResponse(BaseModel):
    """Active onboarding state for a user."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    status: str
    current_step: str
    latest_workflow_run_id: UUID | None = None
    extracted_profile: str | None = None
    missing_info: list[str] = Field(default_factory=list)
    preference_hints: list[str] = Field(default_factory=list)
    clarification_turns: list[dict[str, str]] = Field(default_factory=list)
    pending_user_prompt: str | None = None
    pending_user_prompt_type: str | None = None
    verification_score: float | None = None
    verification_summary: str | None = None
    search_strategy_summary: str | None = None
    hard_preferences: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)
    extraction_model: str | None = None
    last_error_message: str | None = None
    superseded_by_session_id: UUID | None = None
    created_at: datetime
    updated_at: datetime | None

    @field_validator(
        "missing_info",
        "preference_hints",
        "clarification_turns",
        "hard_preferences",
        "soft_preferences",
        mode="before",
    )
    @classmethod
    def _default_list(cls, value: list[str] | None) -> list[str]:
        return value or []


class SubmitOnboardingAnswerRequest(BaseModel):
    """User answer for the current onboarding prompt."""

    answer: str
