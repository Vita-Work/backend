from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.mixin import BaseMixin


class BillingSubscription(Base, BaseMixin):
    """Local subscription snapshot used for access checks and daily monitoring."""

    __tablename__ = "billing_subscriptions"

    user_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="paddle",
        server_default="paddle",
    )
    plan_code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pro",
        server_default="pro",
        index=True,
    )
    status: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    provider_price_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    scheduled_change_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    current_period_starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    current_period_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_billed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_event_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_event_occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    monitoring_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    monitoring_hour_local: Mapped[int] = mapped_column(
        nullable=False,
        default=9,
        server_default="9",
    )
    monitoring_minute_local: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
    )
    monitoring_last_run_local_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class BillingWebhookEvent(Base, BaseMixin):
    """Idempotency and audit log for inbound Paddle webhooks."""

    __tablename__ = "billing_webhook_events"

    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="paddle",
        server_default="paddle",
    )
    provider_event_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="received",
        server_default="received",
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    provider_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
