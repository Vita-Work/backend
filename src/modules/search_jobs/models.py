from uuid import UUID

from sqlalchemy import JSON, Integer, String, Text
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
