"""add auth tables and user roles

Revision ID: 9a1b2c3d4e5f
Revises: 5c2d8aa12b31
Create Date: 2026-03-23 13:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "9a1b2c3d4e5f"
down_revision = "5c2d8aa12b31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("role", sa.String(length=32), server_default="user", nullable=False)
    )
    op.add_column(
        "users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    op.create_table(
        "auth_email_challenges",
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column(
            "purpose", sa.String(length=32), server_default="login_or_signup", nullable=False
        ),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_ip", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_email_challenges")),
    )
    op.create_index(
        op.f("ix_auth_email_challenges_email"), "auth_email_challenges", ["email"], unique=False
    )
    op.create_index(
        op.f("ix_auth_email_challenges_expires_at"),
        "auth_email_challenges",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_email_challenges_purpose"), "auth_email_challenges", ["purpose"], unique=False
    )

    op.create_table(
        "auth_sessions",
        sa.Column("session_token_hash", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("role_snapshot", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_ip", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("session_token_hash", name=op.f("uq_auth_sessions_session_token_hash")),
    )
    op.create_index(
        op.f("ix_auth_sessions_expires_at"), "auth_sessions", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_auth_sessions_role_snapshot"), "auth_sessions", ["role_snapshot"], unique=False
    )
    op.create_index(
        op.f("ix_auth_sessions_session_token_hash"),
        "auth_sessions",
        ["session_token_hash"],
        unique=False,
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_session_token_hash"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_role_snapshot"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_expires_at"), table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index(op.f("ix_auth_email_challenges_purpose"), table_name="auth_email_challenges")
    op.drop_index(op.f("ix_auth_email_challenges_expires_at"), table_name="auth_email_challenges")
    op.drop_index(op.f("ix_auth_email_challenges_email"), table_name="auth_email_challenges")
    op.drop_table("auth_email_challenges")

    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "role")
