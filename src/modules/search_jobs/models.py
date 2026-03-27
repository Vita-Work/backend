from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
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
    monitoring_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

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


class SearchJobSeenJob(Base, BaseMixin):
    """Per-user memory of jobs already delivered by search-job monitoring."""

    __tablename__ = "search_job_seen_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "canonical_job_url", name="uq_search_job_seen_jobs_user_job"),
    )

    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    workflow_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    site: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    canonical_job_url: Mapped[str] = mapped_column(Text, nullable=False)
    job_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_published_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    first_seen_by_user_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_seen_by_user_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    first_delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    times_seen: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    times_delivered: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
