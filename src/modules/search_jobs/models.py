from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.mixin import BaseMixin


class SearchJobWorkflowRun(Base, BaseMixin):
    """Persisted job-search workflow execution state."""

    __tablename__ = "search_job_workflow_runs"

    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    onboarding_session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )

    search_strategy_summary: Mapped[str] = mapped_column(Text, nullable=False)
    hard_preferences: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    soft_preferences: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_sites: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    total_site_results: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_jobs_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_jobs_returned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    summary_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    jobs: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    site_results: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    search_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unification_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_internal_stage: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    current_display_stage: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    current_display_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_display_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_stage_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_stage_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_progress_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class SearchJobProgressEvent(Base, BaseMixin):
    """Persisted frontend-safe progress events for search-job workflows."""

    __tablename__ = "search_job_progress_events"

    workflow_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    internal_stage: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    display_stage: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_label: Mapped[str] = mapped_column(Text, nullable=False)
    display_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    site: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    progress_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    display_icon_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_color_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    site_display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
