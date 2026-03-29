from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.mixin import BaseMixin


class TrackedJobAiRun(Base, BaseMixin):
    """Persist one match-gap or Tailor Pack generation run."""

    __tablename__ = "tracked_job_ai_runs"

    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tracked_job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tracked_jobs.id"),
        nullable=False,
        index=True,
    )
    run_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    credit_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source_onboarding_session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    source_profile_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_job_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    latest_successor_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
