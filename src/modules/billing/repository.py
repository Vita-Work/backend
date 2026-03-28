from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.billing.models import BillingSubscription, BillingWebhookEvent
from src.modules.users.models import User


@dataclass
class BillingMonitoringCandidate:
    user_id: str
    timezone: str
    subscription: BillingSubscription


class BillingSubscriptionsRepository:
    """Persistence for user subscriptions and monitoring preferences."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_id(self, *, user_id: str) -> BillingSubscription | None:
        result = await self.session.execute(
            select(BillingSubscription).where(BillingSubscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_provider_subscription_id(
        self,
        *,
        provider_subscription_id: str,
    ) -> BillingSubscription | None:
        result = await self.session.execute(
            select(BillingSubscription).where(
                BillingSubscription.provider_subscription_id == provider_subscription_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_provider_customer_id(
        self,
        *,
        provider_customer_id: str,
    ) -> BillingSubscription | None:
        result = await self.session.execute(
            select(BillingSubscription).where(
                BillingSubscription.provider_customer_id == provider_customer_id
            )
        )
        return result.scalar_one_or_none()

    def add(self, *, user_id: str) -> BillingSubscription:
        subscription = BillingSubscription(user_id=user_id)
        self.session.add(subscription)
        return subscription

    async def list_monitoring_candidates(
        self,
        *,
        statuses: tuple[str, ...],
    ) -> list[BillingMonitoringCandidate]:
        result = await self.session.execute(
            select(BillingSubscription, User)
            .join(User, User.id.cast(String) == BillingSubscription.user_id)  # type: ignore[name-defined]
            .where(
                BillingSubscription.monitoring_enabled.is_(True),
                BillingSubscription.status.in_(statuses),
            )
        )
        candidates: list[BillingMonitoringCandidate] = []
        for subscription, user in result.all():
            candidates.append(
                BillingMonitoringCandidate(
                    user_id=subscription.user_id,
                    timezone=user.timezone or "UTC",
                    subscription=subscription,
                )
            )
        return candidates


class BillingWebhookEventsRepository:
    """Persistence for inbound webhook idempotency and audit state."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_by_provider_event_id(
        self, *, provider_event_id: str
    ) -> BillingWebhookEvent | None:
        result = await self.session.execute(
            select(BillingWebhookEvent).where(
                BillingWebhookEvent.provider_event_id == provider_event_id
            )
        )
        return result.scalar_one_or_none()

    def add(
        self,
        *,
        provider_event_id: str,
        event_type: str,
        payload: dict[str, object],
        occurred_at: datetime | None,
        provider_customer_id: str | None = None,
        provider_subscription_id: str | None = None,
    ) -> BillingWebhookEvent:
        event = BillingWebhookEvent(
            provider_event_id=provider_event_id,
            event_type=event_type,
            payload=payload,
            occurred_at=occurred_at,
            provider_customer_id=provider_customer_id,
            provider_subscription_id=provider_subscription_id,
        )
        self.session.add(event)
        return event
