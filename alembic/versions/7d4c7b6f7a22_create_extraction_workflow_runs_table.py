"""create extraction workflow runs table

Revision ID: 7d4c7b6f7a22
Revises: c4a71d48e5c2
Create Date: 2026-03-21 20:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7d4c7b6f7a22"
down_revision = "c4a71d48e5c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "extraction_workflow_runs",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("storage_bucket", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("cv_filename", sa.Text(), nullable=False),
        sa.Column("cv_content_type", sa.String(length=255), nullable=False),
        sa.Column("cv_extension", sa.String(length=16), nullable=False),
        sa.Column("cv_size_bytes", sa.Integer(), nullable=False),
        sa.Column("cv_sha256", sa.String(length=64), nullable=False),
        sa.Column("extraction_strategy", sa.String(length=32), nullable=False),
        sa.Column("inline_text_characters", sa.Integer(), nullable=True),
        sa.Column("extracted_profile", sa.Text(), nullable=True),
        sa.Column("missing_info", sa.JSON(), nullable=True),
        sa.Column("preference_hints", sa.JSON(), nullable=True),
        sa.Column("extraction_model", sa.String(length=128), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extraction_workflow_runs")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_extraction_workflow_runs_storage_key")),
    )
    op.create_index(
        op.f("ix_extraction_workflow_runs_status"),
        "extraction_workflow_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extraction_workflow_runs_user_id"),
        "extraction_workflow_runs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_extraction_workflow_runs_user_id"), table_name="extraction_workflow_runs"
    )
    op.drop_index(op.f("ix_extraction_workflow_runs_status"), table_name="extraction_workflow_runs")
    op.drop_table("extraction_workflow_runs")
