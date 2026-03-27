from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.config import Settings, get_settings
from src.modules.billing.models import BillingSubscription
from src.modules.billing.schemas import (
    BillingCheckoutConfigResponse,
    BillingEntitlementsResponse,
    BillingOverviewResponse,
    BillingSubscriptionSummaryResponse,
)

ACTIVE_PRO_SUBSCRIPTION_STATUSES = ("active", "trialing", "past_due")


@dataclass(frozen=True)
class BillingEntitlements:
    plan_code: str
    plan_label: str
    can_access_full_results: bool
    can_use_daily_monitoring: bool
    search_results_limit: int | None


def build_billing_entitlements(
    subscription: BillingSubscription | None,
    *,
    settings: Settings | None = None,
) -> BillingEntitlements:
    config = settings or get_settings()
    if subscription is None or subscription.status not in ACTIVE_PRO_SUBSCRIPTION_STATUSES:
        return BillingEntitlements(
            plan_code="free",
            plan_label="Free",
            can_access_full_results=False,
            can_use_daily_monitoring=False,
            search_results_limit=config.billing_free_job_limit,
        )

    return BillingEntitlements(
        plan_code="pro",
        plan_label="Pro",
        can_access_full_results=True,
        can_use_daily_monitoring=True,
        search_results_limit=None,
    )


def limit_visible_search_jobs(
    *,
    jobs: list[dict[str, object]],
    entitlements: BillingEntitlements,
) -> list[dict[str, object]]:
    if entitlements.search_results_limit is None:
        return list(jobs)
    return list(jobs[: entitlements.search_results_limit])


def user_is_due_for_monitoring(
    *,
    subscription: BillingSubscription,
    timezone: str,
    now: datetime | None = None,
) -> bool:
    if not subscription.monitoring_enabled:
        return False
    if subscription.status not in ACTIVE_PRO_SUBSCRIPTION_STATUSES:
        return False

    current_time = (now or datetime.now(UTC)).astimezone(_safe_zoneinfo(timezone))
    target_hour = subscription.monitoring_hour_local
    target_minute = subscription.monitoring_minute_local
    if (current_time.hour, current_time.minute) < (target_hour, target_minute):
        return False

    return subscription.monitoring_last_run_local_date != current_time.date()


def build_billing_overview(
    *,
    subscription: BillingSubscription | None,
    timezone: str,
    settings: Settings | None = None,
) -> BillingOverviewResponse:
    config = settings or get_settings()
    entitlements = build_billing_entitlements(subscription, settings=config)
    monitoring_hour_local = subscription.monitoring_hour_local if subscription else 9
    monitoring_minute_local = subscription.monitoring_minute_local if subscription else 0

    return BillingOverviewResponse(
        entitlements=BillingEntitlementsResponse(
            plan_code=entitlements.plan_code,  # type: ignore[arg-type]
            plan_label=entitlements.plan_label,
            can_access_full_results=entitlements.can_access_full_results,
            can_use_daily_monitoring=entitlements.can_use_daily_monitoring,
            search_results_limit=entitlements.search_results_limit,
        ),
        subscription=BillingSubscriptionSummaryResponse(
            provider=subscription.provider if subscription else None,
            status=subscription.status if subscription else None,
            provider_customer_id=subscription.provider_customer_id if subscription else None,
            provider_subscription_id=(
                subscription.provider_subscription_id if subscription else None
            ),
            provider_price_id=subscription.provider_price_id if subscription else None,
            cancel_at_period_end=subscription.cancel_at_period_end if subscription else False,
            current_period_starts_at=(
                subscription.current_period_starts_at if subscription else None
            ),
            current_period_ends_at=subscription.current_period_ends_at if subscription else None,
            next_billed_at=subscription.next_billed_at if subscription else None,
            monitoring_enabled=subscription.monitoring_enabled if subscription else False,
            monitoring_hour_local=monitoring_hour_local,
            monitoring_minute_local=monitoring_minute_local,
            monitoring_last_run_local_date=(
                subscription.monitoring_last_run_local_date if subscription else None
            ),
        ),
        checkout=BillingCheckoutConfigResponse(
            environment=config.paddle_environment,
            enabled=bool(
                config.paddle_client_side_token
                and config.paddle_product_id_pro
                and config.paddle_price_id_pro_monthly
            ),
            client_side_token=config.paddle_client_side_token,
            product_id=config.paddle_product_id_pro,
            price_id=config.paddle_price_id_pro_monthly,
            product_name="Vitable Pro" if config.paddle_product_id_pro else None,
            price_label="$20/month" if config.paddle_price_id_pro_monthly else None,
        ),
        monitoring_timezone=timezone,
        monitoring_schedule_local_label=(
            f"{monitoring_hour_local:02d}:{monitoring_minute_local:02d}"
        ),
    )


def _safe_zoneinfo(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")
