"""add search job monitoring memory

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-25 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "search_job_workflow_runs",
        sa.Column("monitoring_mode", sa.Boolean(), server_default="false", nullable=False),
    )

    op.create_table(
        "search_job_seen_jobs",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=True),
        sa.Column("site", sa.String(length=64), nullable=True),
        sa.Column("canonical_job_url", sa.Text(), nullable=False),
        sa.Column("job_fingerprint", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("source_published_at", sa.Text(), nullable=True),
        sa.Column("first_scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_by_user_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_by_user_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("times_seen", sa.Integer(), server_default="1", nullable=False),
        sa.Column("times_delivered", sa.Integer(), server_default="1", nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_job_seen_jobs")),
        sa.UniqueConstraint(
            "user_id",
            "canonical_job_url",
            name="uq_search_job_seen_jobs_user_job",
        ),
    )
    op.create_index(
        op.f("ix_search_job_seen_jobs_user_id"),
        "search_job_seen_jobs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_seen_jobs_workflow_run_id"),
        "search_job_seen_jobs",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_seen_jobs_site"),
        "search_job_seen_jobs",
        ["site"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_seen_jobs_job_fingerprint"),
        "search_job_seen_jobs",
        ["job_fingerprint"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_seen_jobs_last_scraped_at"),
        "search_job_seen_jobs",
        ["last_scraped_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_seen_jobs_last_seen_by_user_at"),
        "search_job_seen_jobs",
        ["last_seen_by_user_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_seen_jobs_last_delivered_at"),
        "search_job_seen_jobs",
        ["last_delivered_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_search_job_seen_jobs_last_delivered_at"),
        table_name="search_job_seen_jobs",
    )
    op.drop_index(
        op.f("ix_search_job_seen_jobs_last_seen_by_user_at"),
        table_name="search_job_seen_jobs",
    )
    op.drop_index(
        op.f("ix_search_job_seen_jobs_last_scraped_at"),
        table_name="search_job_seen_jobs",
    )
    op.drop_index(
        op.f("ix_search_job_seen_jobs_job_fingerprint"),
        table_name="search_job_seen_jobs",
    )
    op.drop_index(op.f("ix_search_job_seen_jobs_site"), table_name="search_job_seen_jobs")
    op.drop_index(
        op.f("ix_search_job_seen_jobs_workflow_run_id"),
        table_name="search_job_seen_jobs",
    )
    op.drop_index(op.f("ix_search_job_seen_jobs_user_id"), table_name="search_job_seen_jobs")
    op.drop_table("search_job_seen_jobs")
    op.drop_column("search_job_workflow_runs", "monitoring_mode")
