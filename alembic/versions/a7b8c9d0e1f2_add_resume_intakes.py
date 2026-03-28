"""add resume intakes

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-28 20:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resume_intakes",
        sa.Column("intake_token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="uploaded", nullable=False),
        sa.Column("claimed_user_id", sa.String(length=255), nullable=True),
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
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resume_intakes")),
    )
    op.create_index(
        op.f("ix_resume_intakes_intake_token_hash"),
        "resume_intakes",
        ["intake_token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_resume_intakes_status"),
        "resume_intakes",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resume_intakes_claimed_user_id"),
        "resume_intakes",
        ["claimed_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resume_intakes_expires_at"),
        "resume_intakes",
        ["expires_at"],
        unique=False,
    )
    op.create_unique_constraint(
        op.f("uq_resume_intakes_storage_key"),
        "resume_intakes",
        ["storage_key"],
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_resume_intakes_storage_key"), "resume_intakes", type_="unique")
    op.drop_index(op.f("ix_resume_intakes_expires_at"), table_name="resume_intakes")
    op.drop_index(op.f("ix_resume_intakes_claimed_user_id"), table_name="resume_intakes")
    op.drop_index(op.f("ix_resume_intakes_status"), table_name="resume_intakes")
    op.drop_index(op.f("ix_resume_intakes_intake_token_hash"), table_name="resume_intakes")
    op.drop_table("resume_intakes")
