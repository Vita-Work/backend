"""add job ai and extended billing

Revision ID: 1c2d3e4f5a6b
Revises: a7b8c9d0e1f2
Create Date: 2026-03-29 23:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "1c2d3e4f5a6b"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_access_passes",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("pass_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="paddle", nullable=False),
        sa.Column("provider_transaction_id", sa.String(length=64), nullable=True),
        sa.Column("provider_price_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_access_passes")),
    )
    op.create_index(
        op.f("ix_billing_access_passes_user_id"),
        "billing_access_passes",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_access_passes_pass_type"),
        "billing_access_passes",
        ["pass_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_access_passes_provider_transaction_id"),
        "billing_access_passes",
        ["provider_transaction_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_access_passes_provider_price_id"),
        "billing_access_passes",
        ["provider_price_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_access_passes_status"),
        "billing_access_passes",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_access_passes_ends_at"),
        "billing_access_passes",
        ["ends_at"],
        unique=False,
    )

    op.create_table(
        "billing_credit_ledger",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("credit_type", sa.String(length=32), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("tracked_job_id", sa.String(length=36), nullable=True),
        sa.Column("ai_run_id", sa.String(length=36), nullable=True),
        sa.Column("access_pass_id", sa.UUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["access_pass_id"],
            ["billing_access_passes.id"],
            name=op.f("fk_billing_credit_ledger_access_pass_id_billing_access_passes"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_credit_ledger")),
    )
    op.create_index(
        op.f("ix_billing_credit_ledger_user_id"),
        "billing_credit_ledger",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_credit_ledger_credit_type"),
        "billing_credit_ledger",
        ["credit_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_credit_ledger_entry_type"),
        "billing_credit_ledger",
        ["entry_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_credit_ledger_tracked_job_id"),
        "billing_credit_ledger",
        ["tracked_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_credit_ledger_ai_run_id"),
        "billing_credit_ledger",
        ["ai_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_credit_ledger_access_pass_id"),
        "billing_credit_ledger",
        ["access_pass_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_credit_ledger_expires_at"),
        "billing_credit_ledger",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "tracked_job_ai_runs",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("tracked_job_id", sa.UUID(), nullable=False),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("credit_cost", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_onboarding_session_id", sa.UUID(), nullable=True),
        sa.Column("source_profile_hash", sa.String(length=64), nullable=False),
        sa.Column("source_job_hash", sa.String(length=64), nullable=False),
        sa.Column("latest_successor_run_id", sa.UUID(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["tracked_job_id"],
            ["tracked_jobs.id"],
            name=op.f("fk_tracked_job_ai_runs_tracked_job_id_tracked_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracked_job_ai_runs")),
    )
    op.create_index(
        op.f("ix_tracked_job_ai_runs_user_id"),
        "tracked_job_ai_runs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_ai_runs_tracked_job_id"),
        "tracked_job_ai_runs",
        ["tracked_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_ai_runs_run_type"),
        "tracked_job_ai_runs",
        ["run_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_ai_runs_status"),
        "tracked_job_ai_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_ai_runs_source_onboarding_session_id"),
        "tracked_job_ai_runs",
        ["source_onboarding_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_ai_runs_source_profile_hash"),
        "tracked_job_ai_runs",
        ["source_profile_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_ai_runs_source_job_hash"),
        "tracked_job_ai_runs",
        ["source_job_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tracked_job_ai_runs_latest_successor_run_id"),
        "tracked_job_ai_runs",
        ["latest_successor_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tracked_job_ai_runs_latest_successor_run_id"),
        table_name="tracked_job_ai_runs",
    )
    op.drop_index(
        op.f("ix_tracked_job_ai_runs_source_job_hash"),
        table_name="tracked_job_ai_runs",
    )
    op.drop_index(
        op.f("ix_tracked_job_ai_runs_source_profile_hash"),
        table_name="tracked_job_ai_runs",
    )
    op.drop_index(
        op.f("ix_tracked_job_ai_runs_source_onboarding_session_id"),
        table_name="tracked_job_ai_runs",
    )
    op.drop_index(op.f("ix_tracked_job_ai_runs_status"), table_name="tracked_job_ai_runs")
    op.drop_index(op.f("ix_tracked_job_ai_runs_run_type"), table_name="tracked_job_ai_runs")
    op.drop_index(
        op.f("ix_tracked_job_ai_runs_tracked_job_id"),
        table_name="tracked_job_ai_runs",
    )
    op.drop_index(op.f("ix_tracked_job_ai_runs_user_id"), table_name="tracked_job_ai_runs")
    op.drop_table("tracked_job_ai_runs")

    op.drop_index(
        op.f("ix_billing_credit_ledger_expires_at"),
        table_name="billing_credit_ledger",
    )
    op.drop_index(
        op.f("ix_billing_credit_ledger_access_pass_id"),
        table_name="billing_credit_ledger",
    )
    op.drop_index(op.f("ix_billing_credit_ledger_ai_run_id"), table_name="billing_credit_ledger")
    op.drop_index(
        op.f("ix_billing_credit_ledger_tracked_job_id"),
        table_name="billing_credit_ledger",
    )
    op.drop_index(
        op.f("ix_billing_credit_ledger_entry_type"),
        table_name="billing_credit_ledger",
    )
    op.drop_index(
        op.f("ix_billing_credit_ledger_credit_type"),
        table_name="billing_credit_ledger",
    )
    op.drop_index(op.f("ix_billing_credit_ledger_user_id"), table_name="billing_credit_ledger")
    op.drop_table("billing_credit_ledger")

    op.drop_index(op.f("ix_billing_access_passes_ends_at"), table_name="billing_access_passes")
    op.drop_index(op.f("ix_billing_access_passes_status"), table_name="billing_access_passes")
    op.drop_index(
        op.f("ix_billing_access_passes_provider_price_id"),
        table_name="billing_access_passes",
    )
    op.drop_index(
        op.f("ix_billing_access_passes_provider_transaction_id"),
        table_name="billing_access_passes",
    )
    op.drop_index(op.f("ix_billing_access_passes_pass_type"), table_name="billing_access_passes")
    op.drop_index(op.f("ix_billing_access_passes_user_id"), table_name="billing_access_passes")
    op.drop_table("billing_access_passes")
