"""create search job workflow runs table

Revision ID: 5c2d8aa12b31
Revises: 2b8fd2c6a4d1
Create Date: 2026-03-21 23:55:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5c2d8aa12b31"
down_revision = "2b8fd2c6a4d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "search_job_workflow_runs",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("onboarding_session_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("search_strategy_summary", sa.Text(), nullable=False),
        sa.Column("hard_preferences", sa.JSON(), nullable=False),
        sa.Column("soft_preferences", sa.JSON(), nullable=False),
        sa.Column("source_sites", sa.JSON(), nullable=True),
        sa.Column("total_site_results", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_jobs_found", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_jobs_returned", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary_markdown", sa.Text(), nullable=True),
        sa.Column("jobs", sa.JSON(), nullable=True),
        sa.Column("site_results", sa.JSON(), nullable=True),
        sa.Column("notes", sa.JSON(), nullable=True),
        sa.Column("search_model", sa.String(length=128), nullable=True),
        sa.Column("unification_model", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_job_workflow_runs")),
    )
    op.create_index(
        op.f("ix_search_job_workflow_runs_onboarding_session_id"),
        "search_job_workflow_runs",
        ["onboarding_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_workflow_runs_status"),
        "search_job_workflow_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_workflow_runs_user_id"),
        "search_job_workflow_runs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_search_job_workflow_runs_user_id"),
        table_name="search_job_workflow_runs",
    )
    op.drop_index(
        op.f("ix_search_job_workflow_runs_status"),
        table_name="search_job_workflow_runs",
    )
    op.drop_index(
        op.f("ix_search_job_workflow_runs_onboarding_session_id"),
        table_name="search_job_workflow_runs",
    )
    op.drop_table("search_job_workflow_runs")
