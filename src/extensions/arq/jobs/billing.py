from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import with_session
from src.logger import get_logger
from src.modules.billing.repository import BillingSubscriptionsRepository
from src.modules.billing.service import ACTIVE_PRO_SUBSCRIPTION_STATUSES, user_is_due_for_monitoring
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
