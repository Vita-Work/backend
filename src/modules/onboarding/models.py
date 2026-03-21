from uuid import UUID

from sqlalchemy import JSON, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.mixin import BaseMixin


class OnboardingSession(Base, BaseMixin):
    """Persisted onboarding process state for a user."""

    __tablename__ = "onboarding_sessions"

    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        server_default="draft",
        index=True,
    )
    current_step: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="extraction",
        server_default="extraction",
    )

    latest_workflow_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    extracted_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_info: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    preference_hints: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    clarification_turns: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)
    pending_user_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_user_prompt_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verification_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_strategy_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    hard_preferences: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    soft_preferences: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_by_session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
