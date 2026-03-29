from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.billing.models import (
    BillingAccessPass,
    BillingCreditLedgerEntry,
    BillingSubscription,
    BillingWebhookEvent,
)
from src.modules.users.models import User


@dataclass
class BillingMonitoringCandidate:
    user_id: str
    timezone: str
    subscription: BillingSubscription


@dataclass
class BillingAccessPassMonitoringCandidate:
    user_id: str
    timezone: str
    subscription: BillingSubscription | None
    access_pass: BillingAccessPass


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


class BillingAccessPassesRepository:
    """Persistence for time-boxed paid access."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_active_for_user(
        self, *, user_id: str, now: datetime | None = None
    ) -> BillingAccessPass | None:
        current_time = now or datetime.now(UTC)
        result = await self.session.execute(
            select(BillingAccessPass)
            .where(
                BillingAccessPass.user_id == user_id,
                BillingAccessPass.status == "active",
                BillingAccessPass.starts_at <= current_time,
                BillingAccessPass.ends_at > current_time,
            )
            .order_by(BillingAccessPass.ends_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_provider_transaction_id(
        self, *, provider_transaction_id: str
    ) -> BillingAccessPass | None:
        result = await self.session.execute(
            select(BillingAccessPass).where(
                BillingAccessPass.provider_transaction_id == provider_transaction_id
            )
        )
        return result.scalar_one_or_none()

    def add(self, **kwargs) -> BillingAccessPass:
        access_pass = BillingAccessPass(**kwargs)
        self.session.add(access_pass)
        return access_pass

    async def list_monitoring_candidates(
        self,
        *,
        pass_types: tuple[str, ...],
        now: datetime | None = None,
    ) -> list[BillingAccessPassMonitoringCandidate]:
        current_time = now or datetime.now(UTC)
        result = await self.session.execute(
            select(BillingAccessPass, User, BillingSubscription)
            .join(User, User.id.cast(String) == BillingAccessPass.user_id)  # type: ignore[name-defined]
            .outerjoin(
                BillingSubscription,
                BillingSubscription.user_id == BillingAccessPass.user_id,
            )
            .where(
                BillingAccessPass.pass_type.in_(pass_types),
                BillingAccessPass.status == "active",
                BillingAccessPass.starts_at <= current_time,
                BillingAccessPass.ends_at > current_time,
            )
        )
        candidates: list[BillingAccessPassMonitoringCandidate] = []
        for access_pass, user, subscription in result.all():
            candidates.append(
                BillingAccessPassMonitoringCandidate(
                    user_id=access_pass.user_id,
                    timezone=user.timezone or "UTC",
                    subscription=subscription,
                    access_pass=access_pass,
                )
            )
        return candidates


class BillingCreditLedgerRepository:
    """Append-only credit ledger helpers."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    def add_entry(self, **kwargs) -> BillingCreditLedgerEntry:
        entry = BillingCreditLedgerEntry(**kwargs)
        self.session.add(entry)
        return entry

    async def sum_available_credits(
        self,
        *,
        user_id: str,
        credit_type: str,
        now: datetime | None = None,
    ) -> int:
        current_time = now or datetime.now(UTC)
        result = await self.session.execute(
            select(func.coalesce(func.sum(BillingCreditLedgerEntry.delta), 0)).where(
                BillingCreditLedgerEntry.user_id == user_id,
                BillingCreditLedgerEntry.credit_type == credit_type,
                (
                    BillingCreditLedgerEntry.expires_at.is_(None)
                    | (BillingCreditLedgerEntry.expires_at > current_time)
                ),
            )
        )
        return int(result.scalar_one() or 0)

    async def find_entry_by_meta_period(
        self,
        *,
        user_id: str,
        credit_type: str,
        entry_type: str,
        period_key: str,
    ) -> BillingCreditLedgerEntry | None:
        result = await self.session.execute(
            select(BillingCreditLedgerEntry)
            .where(
                BillingCreditLedgerEntry.user_id == user_id,
                BillingCreditLedgerEntry.credit_type == credit_type,
                BillingCreditLedgerEntry.entry_type == entry_type,
                BillingCreditLedgerEntry.meta["period_key"].as_string() == period_key,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def find_entry_by_ai_run_and_type(
        self,
        *,
        ai_run_id: str,
        entry_type: str,
    ) -> BillingCreditLedgerEntry | None:
        result = await self.session.execute(
            select(BillingCreditLedgerEntry)
            .where(
                BillingCreditLedgerEntry.ai_run_id == ai_run_id,
                BillingCreditLedgerEntry.entry_type == entry_type,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def find_entry_by_meta_transaction_id(
        self,
        *,
        user_id: str,
        credit_type: str,
        entry_type: str,
        transaction_id: str,
    ) -> BillingCreditLedgerEntry | None:
        result = await self.session.execute(
            select(BillingCreditLedgerEntry)
            .where(
                BillingCreditLedgerEntry.user_id == user_id,
                BillingCreditLedgerEntry.credit_type == credit_type,
                BillingCreditLedgerEntry.entry_type == entry_type,
                BillingCreditLedgerEntry.meta["transaction_id"].as_string() == transaction_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()


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
