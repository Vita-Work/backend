"""add frontend ux progress support

Revision ID: d4e5f6a7b8c9
Revises: b3c4d5e6f7a8
Create Date: 2026-03-24 10:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "extraction_workflow_runs",
        sa.Column("ui_phase", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "extraction_workflow_runs",
        sa.Column("ui_label", sa.Text(), nullable=True),
    )
    op.add_column(
        "extraction_workflow_runs",
        sa.Column("ui_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "extraction_workflow_runs",
        sa.Column("progress_percent", sa.Integer(), nullable=True),
    )
    op.add_column(
        "extraction_workflow_runs",
        sa.Column("progress_stage_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "extraction_workflow_runs",
        sa.Column("progress_stage_total", sa.Integer(), nullable=True),
    )
    op.add_column(
        "extraction_workflow_runs",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "extraction_workflow_runs",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "extraction_workflow_runs",
        sa.Column("last_progress_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_extraction_workflow_runs_ui_phase"),
        "extraction_workflow_runs",
        ["ui_phase"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_workflow_runs_last_progress_at"),
        "extraction_workflow_runs",
        ["last_progress_at"],
        unique=False,
    )

    op.add_column(
        "search_job_workflow_runs",
        sa.Column("current_internal_stage", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "search_job_workflow_runs",
        sa.Column("current_display_stage", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "search_job_workflow_runs",
        sa.Column("current_display_label", sa.Text(), nullable=True),
    )
    op.add_column(
        "search_job_workflow_runs",
        sa.Column("current_display_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "search_job_workflow_runs",
        sa.Column("progress_percent", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_job_workflow_runs",
        sa.Column("progress_stage_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_job_workflow_runs",
        sa.Column("progress_stage_total", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_job_workflow_runs",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "search_job_workflow_runs",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "search_job_workflow_runs",
        sa.Column("last_progress_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_search_job_workflow_runs_current_internal_stage"),
        "search_job_workflow_runs",
        ["current_internal_stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_workflow_runs_current_display_stage"),
        "search_job_workflow_runs",
        ["current_display_stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_workflow_runs_last_progress_at"),
        "search_job_workflow_runs",
        ["last_progress_at"],
        unique=False,
    )

    op.create_table(
        "extraction_progress_events",
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("ui_phase", sa.String(length=64), nullable=False),
        sa.Column("ui_label", sa.Text(), nullable=False),
        sa.Column("ui_description", sa.Text(), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=True),
        sa.Column("progress_stage_index", sa.Integer(), nullable=True),
        sa.Column("progress_stage_total", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extraction_progress_events")),
    )
    op.create_index(
        op.f("ix_extraction_progress_events_workflow_run_id"),
        "extraction_progress_events",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_progress_events_user_id"),
        "extraction_progress_events",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_progress_events_event_type"),
        "extraction_progress_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_progress_events_ui_phase"),
        "extraction_progress_events",
        ["ui_phase"],
        unique=False,
    )

    op.create_table(
        "search_job_progress_events",
        sa.Column("workflow_run_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("internal_stage", sa.String(length=64), nullable=True),
        sa.Column("display_stage", sa.String(length=64), nullable=False),
        sa.Column("display_label", sa.Text(), nullable=False),
        sa.Column("display_description", sa.Text(), nullable=True),
        sa.Column("site", sa.String(length=64), nullable=True),
        sa.Column("progress_order", sa.Integer(), nullable=True),
        sa.Column("display_icon_key", sa.String(length=64), nullable=True),
        sa.Column("display_color_key", sa.String(length=64), nullable=True),
        sa.Column("site_display_name", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_job_progress_events")),
    )
    op.create_index(
        op.f("ix_search_job_progress_events_workflow_run_id"),
        "search_job_progress_events",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_progress_events_user_id"),
        "search_job_progress_events",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_progress_events_event_type"),
        "search_job_progress_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_progress_events_internal_stage"),
        "search_job_progress_events",
        ["internal_stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_progress_events_display_stage"),
        "search_job_progress_events",
        ["display_stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_search_job_progress_events_site"),
        "search_job_progress_events",
        ["site"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_search_job_progress_events_site"), table_name="search_job_progress_events"
    )
    op.drop_index(
        op.f("ix_search_job_progress_events_display_stage"), table_name="search_job_progress_events"
    )
    op.drop_index(
        op.f("ix_search_job_progress_events_internal_stage"),
        table_name="search_job_progress_events",
    )
    op.drop_index(
        op.f("ix_search_job_progress_events_event_type"), table_name="search_job_progress_events"
    )
    op.drop_index(
        op.f("ix_search_job_progress_events_user_id"), table_name="search_job_progress_events"
    )
    op.drop_index(
        op.f("ix_search_job_progress_events_workflow_run_id"),
        table_name="search_job_progress_events",
    )
    op.drop_table("search_job_progress_events")

    op.drop_index(
        op.f("ix_extraction_progress_events_ui_phase"), table_name="extraction_progress_events"
    )
    op.drop_index(
        op.f("ix_extraction_progress_events_event_type"), table_name="extraction_progress_events"
    )
    op.drop_index(
        op.f("ix_extraction_progress_events_user_id"), table_name="extraction_progress_events"
    )
    op.drop_index(
        op.f("ix_extraction_progress_events_workflow_run_id"),
        table_name="extraction_progress_events",
    )
    op.drop_table("extraction_progress_events")

    op.drop_index(
        op.f("ix_search_job_workflow_runs_last_progress_at"), table_name="search_job_workflow_runs"
    )
    op.drop_index(
        op.f("ix_search_job_workflow_runs_current_display_stage"),
        table_name="search_job_workflow_runs",
    )
    op.drop_index(
        op.f("ix_search_job_workflow_runs_current_internal_stage"),
        table_name="search_job_workflow_runs",
    )
    op.drop_column("search_job_workflow_runs", "last_progress_at")
    op.drop_column("search_job_workflow_runs", "finished_at")
    op.drop_column("search_job_workflow_runs", "started_at")
    op.drop_column("search_job_workflow_runs", "progress_stage_total")
    op.drop_column("search_job_workflow_runs", "progress_stage_index")
    op.drop_column("search_job_workflow_runs", "progress_percent")
    op.drop_column("search_job_workflow_runs", "current_display_description")
    op.drop_column("search_job_workflow_runs", "current_display_label")
    op.drop_column("search_job_workflow_runs", "current_display_stage")
    op.drop_column("search_job_workflow_runs", "current_internal_stage")

    op.drop_index(
        op.f("ix_extraction_workflow_runs_last_progress_at"), table_name="extraction_workflow_runs"
    )
    op.drop_index(
        op.f("ix_extraction_workflow_runs_ui_phase"), table_name="extraction_workflow_runs"
    )
    op.drop_column("extraction_workflow_runs", "last_progress_at")
    op.drop_column("extraction_workflow_runs", "finished_at")
    op.drop_column("extraction_workflow_runs", "started_at")
    op.drop_column("extraction_workflow_runs", "progress_stage_total")
    op.drop_column("extraction_workflow_runs", "progress_stage_index")
    op.drop_column("extraction_workflow_runs", "progress_percent")
    op.drop_column("extraction_workflow_runs", "ui_description")
    op.drop_column("extraction_workflow_runs", "ui_label")
    op.drop_column("extraction_workflow_runs", "ui_phase")
