from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from src.modules.billing.service import (
    build_billing_entitlements,
    limit_visible_search_jobs,
    user_is_due_for_monitoring,
)


def test_build_billing_entitlements_returns_free_defaults() -> None:
    entitlements = build_billing_entitlements(subscription=None)

    assert entitlements.plan_code == "free"
    assert entitlements.can_access_full_results is False
    assert entitlements.can_use_daily_monitoring is False
    assert entitlements.search_results_limit == 3


def test_build_billing_entitlements_returns_pro_for_active_subscription() -> None:
    entitlements = build_billing_entitlements(subscription=SimpleNamespace(status="active"))

    assert entitlements.plan_code == "pro"
    assert entitlements.can_access_full_results is True
    assert entitlements.can_use_daily_monitoring is True
    assert entitlements.search_results_limit is None


def test_limit_visible_search_jobs_applies_free_limit() -> None:
    jobs = [{"job_url": f"https://example.com/{index}"} for index in range(5)]
    entitlements = build_billing_entitlements(subscription=None)

    visible_jobs = limit_visible_search_jobs(jobs=jobs, entitlements=entitlements)

    assert visible_jobs == jobs[:3]


def test_user_is_due_for_monitoring_uses_local_time_and_daily_guard() -> None:
    subscription = SimpleNamespace(
        monitoring_enabled=True,
        status="active",
        monitoring_hour_local=9,
        monitoring_minute_local=0,
        monitoring_last_run_local_date=None,
    )
    now = datetime(2026, 3, 27, 3, 15, tzinfo=UTC)  # 09:15 Asia/Bishkek

    assert user_is_due_for_monitoring(
        subscription=subscription,
        timezone="Asia/Bishkek",
        now=now,
    )

    subscription.monitoring_last_run_local_date = date(2026, 3, 27)
    assert not user_is_due_for_monitoring(
        subscription=subscription,
        timezone="Asia/Bishkek",
        now=now,
    )
