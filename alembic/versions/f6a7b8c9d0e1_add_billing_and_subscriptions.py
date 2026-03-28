"""add billing and subscriptions

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-27 22:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_subscriptions",
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default="paddle",
            nullable=False,
        ),
        sa.Column(
            "plan_code",
            sa.String(length=32),
            server_default="pro",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("provider_customer_id", sa.String(length=64), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=64), nullable=True),
        sa.Column("provider_transaction_id", sa.String(length=64), nullable=True),
        sa.Column("provider_price_id", sa.String(length=64), nullable=True),
        sa.Column("scheduled_change_action", sa.String(length=64), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("current_period_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_billed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_id", sa.String(length=64), nullable=True),
        sa.Column("last_event_type", sa.String(length=128), nullable=True),
        sa.Column("last_event_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "monitoring_enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "monitoring_hour_local",
            sa.Integer(),
            server_default="9",
            nullable=False,
        ),
        sa.Column(
            "monitoring_minute_local",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("monitoring_last_run_local_date", sa.Date(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_subscriptions")),
        sa.UniqueConstraint("user_id", name="uq_billing_subscriptions_user_id"),
        sa.UniqueConstraint(
            "provider_subscription_id",
            name="uq_billing_subscriptions_provider_subscription_id",
        ),
    )
    op.create_index(
        op.f("ix_billing_subscriptions_user_id"),
        "billing_subscriptions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_plan_code"),
        "billing_subscriptions",
        ["plan_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_status"),
        "billing_subscriptions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_provider_customer_id"),
        "billing_subscriptions",
        ["provider_customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_provider_subscription_id"),
        "billing_subscriptions",
        ["provider_subscription_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_provider_transaction_id"),
        "billing_subscriptions",
        ["provider_transaction_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_subscriptions_provider_price_id"),
        "billing_subscriptions",
        ["provider_price_id"],
        unique=False,
    )

    op.create_table(
        "billing_webhook_events",
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default="paddle",
            nullable=False,
        ),
        sa.Column("provider_event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="received",
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=255), nullable=True),
        sa.Column("provider_customer_id", sa.String(length=64), nullable=True),
        sa.Column("provider_subscription_id", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_billing_webhook_events")),
        sa.UniqueConstraint(
            "provider_event_id",
            name="uq_billing_webhook_events_provider_event_id",
        ),
    )
    op.create_index(
        op.f("ix_billing_webhook_events_provider_event_id"),
        "billing_webhook_events",
        ["provider_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_webhook_events_event_type"),
        "billing_webhook_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_webhook_events_status"),
        "billing_webhook_events",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_webhook_events_user_id"),
        "billing_webhook_events",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_webhook_events_provider_customer_id"),
        "billing_webhook_events",
        ["provider_customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_billing_webhook_events_provider_subscription_id"),
        "billing_webhook_events",
        ["provider_subscription_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_billing_webhook_events_provider_subscription_id"),
        table_name="billing_webhook_events",
    )
    op.drop_index(
        op.f("ix_billing_webhook_events_provider_customer_id"),
        table_name="billing_webhook_events",
    )
    op.drop_index(op.f("ix_billing_webhook_events_user_id"), table_name="billing_webhook_events")
    op.drop_index(op.f("ix_billing_webhook_events_status"), table_name="billing_webhook_events")
    op.drop_index(op.f("ix_billing_webhook_events_event_type"), table_name="billing_webhook_events")
    op.drop_index(
        op.f("ix_billing_webhook_events_provider_event_id"),
        table_name="billing_webhook_events",
    )
    op.drop_table("billing_webhook_events")

    op.drop_index(
        op.f("ix_billing_subscriptions_provider_price_id"),
        table_name="billing_subscriptions",
    )
    op.drop_index(
        op.f("ix_billing_subscriptions_provider_transaction_id"),
        table_name="billing_subscriptions",
    )
    op.drop_index(
        op.f("ix_billing_subscriptions_provider_subscription_id"),
        table_name="billing_subscriptions",
    )
    op.drop_index(
        op.f("ix_billing_subscriptions_provider_customer_id"),
        table_name="billing_subscriptions",
    )
    op.drop_index(op.f("ix_billing_subscriptions_status"), table_name="billing_subscriptions")
    op.drop_index(op.f("ix_billing_subscriptions_plan_code"), table_name="billing_subscriptions")
    op.drop_index(op.f("ix_billing_subscriptions_user_id"), table_name="billing_subscriptions")
    op.drop_table("billing_subscriptions")
