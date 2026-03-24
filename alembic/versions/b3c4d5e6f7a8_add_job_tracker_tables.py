"""add job tracker tables

Revision ID: b3c4d5e6f7a8
Revises: 9a1b2c3d4e5f
Create Date: 2026-03-23 18:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "9a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tracked_jobs",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("source_search_job_run_id", sa.UUID(), nullable=True),
        sa.Column("source_job_url", sa.Text(), nullable=True),
        sa.Column("site", sa.String(length=64), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("salary_text", sa.Text(), nullable=True),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        sa.Column("apply_url", sa.Text(), nullable=True),
        sa.Column("description_snapshot", sa.Text(), nullable=True),
        sa.Column("skills_snapshot", sa.JSON(), nullable=False),
        sa.Column("fit_level", sa.String(length=16), nullable=True),
        sa.Column("why_apply_snapshot", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="saved", nullable=False),
        sa.Column("priority", sa.String(length=16), server_default="medium", nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes_summary", sa.Text(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracked_jobs")),
    )
    op.create_index(op.f("ix_tracked_jobs_user_id"), "tracked_jobs", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_tracked_jobs_source_type"),
        "tracked_jobs",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_jobs_source_search_job_run_id"),
        "tracked_jobs",
        ["source_search_job_run_id"],
        unique=False,
    )
    op.create_index(op.f("ix_tracked_jobs_site"), "tracked_jobs", ["site"], unique=False)
    op.create_index(
        op.f("ix_tracked_jobs_status"),
        "tracked_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_jobs_priority"),
        "tracked_jobs",
        ["priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_jobs_last_status_changed_at"),
        "tracked_jobs",
        ["last_status_changed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_jobs_next_follow_up_at"),
        "tracked_jobs",
        ["next_follow_up_at"],
        unique=False,
    )

    op.create_table(
        "tracked_job_activities",
        sa.Column("tracked_job_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("activity_type", sa.String(length=32), server_default="note", nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status_from", sa.String(length=32), nullable=True),
        sa.Column("status_to", sa.String(length=32), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interview_format", sa.String(length=32), nullable=True),
        sa.Column("outcome", sa.String(length=64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracked_job_activities")),
    )
    op.create_index(
        op.f("ix_tracked_job_activities_tracked_job_id"),
        "tracked_job_activities",
        ["tracked_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_activities_user_id"),
        "tracked_job_activities",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_activities_activity_type"),
        "tracked_job_activities",
        ["activity_type"],
        unique=False,
    )

    op.create_table(
        "tracked_job_contacts",
        sa.Column("tracked_job_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("relation_type", sa.String(length=32), server_default="other", nullable=False),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracked_job_contacts")),
    )
    op.create_index(
        op.f("ix_tracked_job_contacts_tracked_job_id"),
        "tracked_job_contacts",
        ["tracked_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_contacts_user_id"),
        "tracked_job_contacts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_contacts_relation_type"),
        "tracked_job_contacts",
        ["relation_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tracked_job_contacts_relation_type"),
        table_name="tracked_job_contacts",
    )
    op.drop_index(
        op.f("ix_tracked_job_contacts_user_id"),
        table_name="tracked_job_contacts",
    )
    op.drop_index(
        op.f("ix_tracked_job_contacts_tracked_job_id"),
        table_name="tracked_job_contacts",
    )
    op.drop_table("tracked_job_contacts")

    op.drop_index(
        op.f("ix_tracked_job_activities_activity_type"),
        table_name="tracked_job_activities",
    )
    op.drop_index(
        op.f("ix_tracked_job_activities_user_id"),
        table_name="tracked_job_activities",
    )
    op.drop_index(
        op.f("ix_tracked_job_activities_tracked_job_id"),
        table_name="tracked_job_activities",
    )
    op.drop_table("tracked_job_activities")

    op.drop_index(op.f("ix_tracked_jobs_next_follow_up_at"), table_name="tracked_jobs")
    op.drop_index(
        op.f("ix_tracked_jobs_last_status_changed_at"),
        table_name="tracked_jobs",
    )
    op.drop_index(op.f("ix_tracked_jobs_priority"), table_name="tracked_jobs")
    op.drop_index(op.f("ix_tracked_jobs_status"), table_name="tracked_jobs")
    op.drop_index(op.f("ix_tracked_jobs_site"), table_name="tracked_jobs")
    op.drop_index(
        op.f("ix_tracked_jobs_source_search_job_run_id"),
        table_name="tracked_jobs",
    )
    op.drop_index(op.f("ix_tracked_jobs_source_type"), table_name="tracked_jobs")
    op.drop_index(op.f("ix_tracked_jobs_user_id"), table_name="tracked_jobs")
    op.drop_table("tracked_jobs")
