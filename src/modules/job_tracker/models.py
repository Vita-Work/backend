from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.mixin import BaseMixin
from src.modules.job_tracker.constants import (
    TRACKED_JOB_ACTIVITY_NOTE,
    TRACKED_JOB_CONTACT_RELATION_OTHER,
    TRACKED_JOB_PRIORITY_MEDIUM,
    TRACKED_JOB_SOURCE_MANUAL,
    TRACKED_JOB_STATUS_SAVED,
)


class TrackedJob(Base, BaseMixin):
    __tablename__ = "tracked_jobs"

    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TRACKED_JOB_SOURCE_MANUAL,
        server_default=TRACKED_JOB_SOURCE_MANUAL,
        index=True,
    )
    source_search_job_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True, index=True
    )
    source_job_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    site: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    apply_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills_snapshot: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    fit_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    why_apply_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TRACKED_JOB_STATUS_SAVED,
        server_default=TRACKED_JOB_STATUS_SAVED,
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TRACKED_JOB_PRIORITY_MEDIUM,
        server_default=TRACKED_JOB_PRIORITY_MEDIUM,
        index=True,
    )
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    notes_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TrackedJobActivity(Base, BaseMixin):
    __tablename__ = "tracked_job_activities"

    tracked_job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TRACKED_JOB_ACTIVITY_NOTE,
        server_default=TRACKED_JOB_ACTIVITY_NOTE,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status_to: Mapped[str | None] = mapped_column(String(32), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class TrackedJobContact(Base, BaseMixin):
    __tablename__ = "tracked_job_contacts"

    tracked_job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    relation_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TRACKED_JOB_CONTACT_RELATION_OTHER,
        server_default=TRACKED_JOB_CONTACT_RELATION_OTHER,
        index=True,
    )
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
