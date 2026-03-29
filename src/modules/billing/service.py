from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.config import Settings, get_settings
from src.modules.auth.security import utcnow
from src.modules.billing.models import BillingAccessPass, BillingSubscription
from src.modules.billing.repository import BillingCreditLedgerRepository
from src.modules.billing.schemas import (
    BillingAccessPassSummaryResponse,
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
    access_plan_code: str
    access_plan_label: str
    can_access_full_results: bool
    can_use_daily_monitoring: bool
    can_run_match_gap_reports: bool
    can_generate_job_packs: bool
    search_results_limit: int | None
    free_match_gap_limit: int | None
    active_pass_ends_at: datetime | None = None


def build_billing_entitlements(
    subscription: BillingSubscription | None,
    access_pass: BillingAccessPass | None = None,
    *,
    has_job_pack_credits: bool = False,
    settings: Settings | None = None,
) -> BillingEntitlements:
    config = settings or get_settings()
    has_active_subscription = (
        subscription is not None and subscription.status in ACTIVE_PRO_SUBSCRIPTION_STATUSES
    )
    has_active_pass = access_pass is not None and access_pass.status == "active"

    if not has_active_subscription and not has_active_pass:
        return BillingEntitlements(
            plan_code="free",
            plan_label="Free",
            access_plan_code="free",
            access_plan_label="Free",
            can_access_full_results=False,
            can_use_daily_monitoring=False,
            can_run_match_gap_reports=True,
            can_generate_job_packs=has_job_pack_credits,
            search_results_limit=config.billing_free_job_limit,
            free_match_gap_limit=config.billing_free_match_gap_limit,
        )

    if has_active_subscription:
        access_plan_code = "pro_search"
        access_plan_label = "Pro Search"
    else:
        access_plan_code = "weekly_sprint"
        access_plan_label = "Weekly Sprint"

    return BillingEntitlements(
        plan_code="pro",
        plan_label=access_plan_label,
        access_plan_code=access_plan_code,
        access_plan_label=access_plan_label,
        can_access_full_results=True,
        can_use_daily_monitoring=True,
        can_run_match_gap_reports=True,
        can_generate_job_packs=True,
        search_results_limit=None,
        free_match_gap_limit=None,
        active_pass_ends_at=access_pass.ends_at if access_pass is not None else None,
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
    if subscription.status not in ACTIVE_PRO_SUBSCRIPTION_STATUSES:
        return False
    return monitoring_schedule_is_due(
        monitoring_enabled=subscription.monitoring_enabled,
        monitoring_hour_local=subscription.monitoring_hour_local,
        monitoring_minute_local=subscription.monitoring_minute_local,
        monitoring_last_run_local_date=subscription.monitoring_last_run_local_date,
        timezone=timezone,
        now=now,
    )


def monitoring_schedule_is_due(
    *,
    monitoring_enabled: bool,
    monitoring_hour_local: int,
    monitoring_minute_local: int,
    monitoring_last_run_local_date,
    timezone: str,
    now: datetime | None = None,
) -> bool:
    if not monitoring_enabled:
        return False

    current_time = (now or datetime.now(UTC)).astimezone(_safe_zoneinfo(timezone))
    if (current_time.hour, current_time.minute) < (monitoring_hour_local, monitoring_minute_local):
        return False

    return monitoring_last_run_local_date != current_time.date()


def build_billing_overview(
    *,
    subscription: BillingSubscription | None,
    access_pass: BillingAccessPass | None = None,
    remaining_job_pack_credits: int = 0,
    timezone: str,
    settings: Settings | None = None,
) -> BillingOverviewResponse:
    config = settings or get_settings()
    entitlements = build_billing_entitlements(
        subscription,
        access_pass=access_pass,
        has_job_pack_credits=remaining_job_pack_credits > 0,
        settings=config,
    )
    monitoring_hour_local = subscription.monitoring_hour_local if subscription else 9
    monitoring_minute_local = subscription.monitoring_minute_local if subscription else 0
    included_job_pack_credits_per_period = (
        config.billing_pro_search_included_job_pack_credits
        if entitlements.access_plan_code == "pro_search"
        else config.billing_weekly_sprint_included_job_pack_credits
        if entitlements.access_plan_code == "weekly_sprint"
        else 0
    )

    return BillingOverviewResponse(
        entitlements=BillingEntitlementsResponse(
            plan_code=entitlements.plan_code,  # type: ignore[arg-type]
            plan_label=entitlements.plan_label,
            access_plan_code=entitlements.access_plan_code,  # type: ignore[arg-type]
            access_plan_label=entitlements.access_plan_label,
            can_access_full_results=entitlements.can_access_full_results,
            can_use_daily_monitoring=entitlements.can_use_daily_monitoring,
            can_run_match_gap_reports=entitlements.can_run_match_gap_reports,
            can_generate_job_packs=entitlements.can_generate_job_packs,
            search_results_limit=entitlements.search_results_limit,
            free_match_gap_limit=entitlements.free_match_gap_limit,
            remaining_job_pack_credits=remaining_job_pack_credits,
            included_job_pack_credits_per_period=included_job_pack_credits_per_period,
            top_up_job_pack_credits=config.billing_tailor_pack_topup_credits,
            active_pass_ends_at=entitlements.active_pass_ends_at,
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
            monitoring_enabled=(
                subscription.monitoring_enabled
                if subscription
                else entitlements.access_plan_code == "weekly_sprint"
            ),
            monitoring_hour_local=monitoring_hour_local,
            monitoring_minute_local=monitoring_minute_local,
            monitoring_last_run_local_date=(
                subscription.monitoring_last_run_local_date if subscription else None
            ),
        ),
        access_pass=BillingAccessPassSummaryResponse(
            pass_type=access_pass.pass_type if access_pass else None,
            status=access_pass.status if access_pass else None,
            provider_transaction_id=access_pass.provider_transaction_id if access_pass else None,
            provider_price_id=access_pass.provider_price_id if access_pass else None,
            starts_at=access_pass.starts_at if access_pass else None,
            ends_at=access_pass.ends_at if access_pass else None,
        ),
        checkout=BillingCheckoutConfigResponse(
            environment=config.paddle_environment,
            enabled=bool(
                config.paddle_client_side_token
                and (
                    config.paddle_price_id_pro_search_monthly or config.paddle_price_id_pro_monthly
                )
            ),
            client_side_token=config.paddle_client_side_token,
            product_id=config.paddle_product_id_pro_search or config.paddle_product_id_pro,
            price_id=config.paddle_price_id_pro_search_monthly
            or config.paddle_price_id_pro_monthly,
            product_name=(
                "Vitable Pro Search"
                if (config.paddle_product_id_pro_search or config.paddle_product_id_pro)
                else None
            ),
            price_label=(
                "$19/month"
                if (config.paddle_price_id_pro_search_monthly or config.paddle_price_id_pro_monthly)
                else None
            ),
            weekly_sprint_product_id=config.paddle_product_id_weekly_sprint,
            weekly_sprint_price_id=config.paddle_price_id_weekly_sprint,
            weekly_sprint_price_label=(
                "$12/week" if config.paddle_price_id_weekly_sprint else None
            ),
            tailor_pack_product_id=config.paddle_product_id_tailor_pack,
            tailor_pack_price_id=config.paddle_price_id_tailor_pack_topup,
            tailor_pack_price_label=(
                f"{config.billing_tailor_pack_topup_credits} credits"
                if config.paddle_price_id_tailor_pack_topup
                else None
            ),
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


async def ensure_job_pack_allowances(
    *,
    user_id: str,
    subscription: BillingSubscription | None,
    access_pass: BillingAccessPass | None,
    credit_repository: BillingCreditLedgerRepository,
    settings: Settings | None = None,
) -> int:
    config = settings or get_settings()
    now = utcnow()

    if subscription is not None and subscription.status in ACTIVE_PRO_SUBSCRIPTION_STATUSES:
        cycle_start = subscription.current_period_starts_at or subscription.activated_at or now
        period_key = f"pro_search:{cycle_start.date().isoformat()}"
        existing = await credit_repository.find_entry_by_meta_period(
            user_id=user_id,
            credit_type="job_pack",
            entry_type="monthly_included",
            period_key=period_key,
        )
        if existing is None:
            credit_repository.add_entry(
                user_id=user_id,
                credit_type="job_pack",
                delta=config.billing_pro_search_included_job_pack_credits,
                entry_type="monthly_included",
                meta={"period_key": period_key},
                expires_at=subscription.current_period_ends_at,
            )

    if access_pass is not None and access_pass.status == "active":
        period_key = f"weekly_sprint:{access_pass.id}"
        existing = await credit_repository.find_entry_by_meta_period(
            user_id=user_id,
            credit_type="job_pack",
            entry_type="weekly_sprint_included",
            period_key=period_key,
        )
        if existing is None:
            credit_repository.add_entry(
                user_id=user_id,
                credit_type="job_pack",
                delta=config.billing_weekly_sprint_included_job_pack_credits,
                entry_type="weekly_sprint_included",
                access_pass_id=access_pass.id,
                meta={"period_key": period_key},
                expires_at=access_pass.ends_at,
            )

    return await credit_repository.sum_available_credits(
        user_id=user_id,
        credit_type="job_pack",
        now=now,
    )
