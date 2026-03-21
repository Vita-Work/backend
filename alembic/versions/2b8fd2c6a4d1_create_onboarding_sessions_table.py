"""create onboarding sessions table

Revision ID: 2b8fd2c6a4d1
Revises: 7d4c7b6f7a22
Create Date: 2026-03-21 22:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2b8fd2c6a4d1"
down_revision = "7d4c7b6f7a22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "onboarding_sessions",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column(
            "current_step",
            sa.String(length=32),
            server_default="extraction",
            nullable=False,
        ),
        sa.Column("latest_workflow_run_id", sa.UUID(), nullable=True),
        sa.Column("extracted_profile", sa.Text(), nullable=True),
        sa.Column("missing_info", sa.JSON(), nullable=True),
        sa.Column("preference_hints", sa.JSON(), nullable=True),
        sa.Column("clarification_turns", sa.JSON(), nullable=True),
        sa.Column("pending_user_prompt", sa.Text(), nullable=True),
        sa.Column("pending_user_prompt_type", sa.String(length=32), nullable=True),
        sa.Column("verification_score", sa.Float(), nullable=True),
        sa.Column("verification_summary", sa.Text(), nullable=True),
        sa.Column("search_strategy_summary", sa.Text(), nullable=True),
        sa.Column("hard_preferences", sa.JSON(), nullable=True),
        sa.Column("soft_preferences", sa.JSON(), nullable=True),
        sa.Column("extraction_model", sa.String(length=128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("superseded_by_session_id", sa.UUID(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_onboarding_sessions")),
    )
    op.create_index(
        op.f("ix_onboarding_sessions_status"),
        "onboarding_sessions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_onboarding_sessions_user_id"),
        "onboarding_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_onboarding_sessions_user_id_active",
        "onboarding_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('draft', 'extracting', 'awaiting_clarification', "
            "'clarifying', 'verifying', 'planning', 'awaiting_confirmation')"
        ),
    )
    op.add_column(
        "extraction_workflow_runs",
        sa.Column("onboarding_session_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        op.f("ix_extraction_workflow_runs_onboarding_session_id"),
        "extraction_workflow_runs",
        ["onboarding_session_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_extraction_workflow_runs_onboarding_session_id"),
        table_name="extraction_workflow_runs",
    )
    op.drop_column("extraction_workflow_runs", "onboarding_session_id")
    op.drop_index("ix_onboarding_sessions_user_id_active", table_name="onboarding_sessions")
    op.drop_index(op.f("ix_onboarding_sessions_user_id"), table_name="onboarding_sessions")
    op.drop_index(op.f("ix_onboarding_sessions_status"), table_name="onboarding_sessions")
    op.drop_table("onboarding_sessions")
