from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import with_session
from src.logger import get_logger
from src.modules.billing.repository import (
    BillingAccessPassesRepository,
    BillingSubscriptionsRepository,
)
from src.modules.billing.service import (
    ACTIVE_PRO_SUBSCRIPTION_STATUSES,
    monitoring_schedule_is_due,
    user_is_due_for_monitoring,
)
from src.modules.search_jobs.use_cases.queue_search_job_workflow import (
    SearchJobMonitoringNotAllowedError,
    SearchJobWorkflowEnqueueError,
    SearchJobWorkflowNotReadyError,
    queue_search_job_workflow,
)

logger = get_logger("arq.jobs.billing")


@with_session
async def enqueue_due_monitoring_runs(
    ctx: dict,
    *,
    session: AsyncSession,
) -> None:
    """Find subscribed users whose daily monitoring is due and enqueue their runs."""
    repository = BillingSubscriptionsRepository(session=session)
    access_pass_repository = BillingAccessPassesRepository(session=session)
    now = datetime.now(UTC)
    redis = ctx["redis"]
    candidates = await repository.list_monitoring_candidates(
        statuses=ACTIVE_PRO_SUBSCRIPTION_STATUSES,
    )
    for candidate in candidates:
        if not user_is_due_for_monitoring(
            subscription=candidate.subscription,
            timezone=candidate.timezone,
            now=now,
        ):
            continue

        try:
            await queue_search_job_workflow(
                session=session,
                arq_redis=redis,
                user_id=candidate.user_id,
                monitoring_mode=True,
            )
        except (
            SearchJobMonitoringNotAllowedError,
            SearchJobWorkflowEnqueueError,
            SearchJobWorkflowNotReadyError,
        ) as exc:
            logger.warning(
                "monitoring_run_skipped",
                user_id=candidate.user_id,
                error=str(exc),
            )
            continue

        try:
            zone = ZoneInfo(candidate.timezone)
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        candidate.subscription.monitoring_last_run_local_date = now.astimezone(zone).date()
        await session.commit()

    access_pass_candidates = await access_pass_repository.list_monitoring_candidates(
        pass_types=("weekly_sprint",),
        now=now,
    )
    for candidate in access_pass_candidates:
        subscription = candidate.subscription
        if subscription is None:
            subscription = repository.add(user_id=candidate.user_id)
            subscription.plan_code = candidate.access_pass.pass_type
            subscription.status = "inactive"
            subscription.provider = candidate.access_pass.provider
            subscription.provider_transaction_id = candidate.access_pass.provider_transaction_id
            subscription.provider_price_id = candidate.access_pass.provider_price_id
            subscription.started_at = candidate.access_pass.starts_at
            await session.flush()

        monitoring_enabled = subscription.monitoring_enabled if subscription is not None else True
        monitoring_hour_local = (
            subscription.monitoring_hour_local if subscription is not None else 9
        )
        monitoring_minute_local = (
            subscription.monitoring_minute_local if subscription is not None else 0
        )
        monitoring_last_run_local_date = (
            subscription.monitoring_last_run_local_date if subscription is not None else None
        )
        if not monitoring_schedule_is_due(
            monitoring_enabled=monitoring_enabled,
            monitoring_hour_local=monitoring_hour_local,
            monitoring_minute_local=monitoring_minute_local,
            monitoring_last_run_local_date=monitoring_last_run_local_date,
            timezone=candidate.timezone,
            now=now,
        ):
            continue

        try:
            await queue_search_job_workflow(
                session=session,
                arq_redis=redis,
                user_id=candidate.user_id,
                monitoring_mode=True,
            )
        except (
            SearchJobMonitoringNotAllowedError,
            SearchJobWorkflowEnqueueError,
            SearchJobWorkflowNotReadyError,
        ) as exc:
            logger.warning(
                "access_pass_monitoring_run_skipped",
                user_id=candidate.user_id,
                error=str(exc),
            )
            continue

        try:
            zone = ZoneInfo(candidate.timezone)
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        subscription.monitoring_last_run_local_date = now.astimezone(zone).date()
        await session.commit()
