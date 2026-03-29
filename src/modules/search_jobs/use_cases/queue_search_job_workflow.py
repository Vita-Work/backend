from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import get_logger
from src.modules.billing.repository import (
    BillingAccessPassesRepository,
    BillingSubscriptionsRepository,
)
from src.modules.billing.service import build_billing_entitlements
from src.modules.onboarding.repository import OnboardingSessionsRepository
from src.modules.search_jobs.models import SearchJobWorkflowRun
from src.modules.search_jobs.progress import update_search_progress
from src.modules.search_jobs.repository import SearchJobWorkflowRunsRepository
from src.modules.users.repository import UsersRepository
from src.services import job_parsers as _job_parsers  # noqa: F401
from src.services.job_parsers.registry import get_registered_parser_names
from src.workflows.search_job import build_search_job_context

logger = get_logger("search_jobs.workflow_queue")


class SearchJobWorkflowEnqueueError(RuntimeError):
    """Raised when a search-job workflow cannot be queued."""


class SearchJobWorkflowNotReadyError(RuntimeError):
    """Raised when the user has no completed search setup to build from."""


class SearchJobMonitoringNotAllowedError(RuntimeError):
    """Raised when a user without Pro access attempts to use daily monitoring."""


async def queue_search_job_workflow(
    *,
    session: AsyncSession,
    arq_redis: ArqRedis,
    user_id: str,
    monitoring_mode: bool = False,
    parent_request_id: str | None = None,
) -> SearchJobWorkflowRun:
    """Persist and enqueue a search-job workflow run."""
    subscription = None
    access_pass = None
    monitoring_local_date = None
    repository = SearchJobWorkflowRunsRepository(session=session)
    if monitoring_mode:
        subscription_repository = BillingSubscriptionsRepository(session=session)
        subscription = await subscription_repository.get_by_user_id_for_update(user_id=user_id)
        access_pass = await BillingAccessPassesRepository(session=session).get_active_for_user(
            user_id=user_id
        )
        entitlements = build_billing_entitlements(
            subscription=subscription,
            access_pass=access_pass,
        )
        if not entitlements.can_use_daily_monitoring:
            raise SearchJobMonitoringNotAllowedError(
                "Daily monitoring is available on Vitable Pro."
            )
        monitoring_timezone = await _get_user_timezone(session=session, user_id=user_id)
        monitoring_local_date = _monitoring_local_date(timezone=monitoring_timezone)
        monitoring_window_start, monitoring_window_end = _monitoring_day_window_utc(
            local_date=monitoring_local_date,
            timezone=monitoring_timezone,
        )
        existing_monitoring_run = await repository.get_latest_monitoring_run_for_user_in_window(
            user_id=user_id,
            created_at_gte=monitoring_window_start,
            created_at_lt=monitoring_window_end,
        )
        if existing_monitoring_run is not None:
            if (
                subscription is not None
                and subscription.monitoring_last_run_local_date != monitoring_local_date
            ):
                subscription.monitoring_last_run_local_date = monitoring_local_date
                await session.commit()
            logger.info(
                "search_job_workflow_reusing_same_day_monitoring_run",
                workflow_run_id=existing_monitoring_run.id,
                user_id=user_id,
                local_date=monitoring_local_date.isoformat(),
            )
            return existing_monitoring_run

    onboarding_repository = OnboardingSessionsRepository(session=session)
    onboarding_session = await onboarding_repository.get_latest_completed_for_user(user_id=user_id)
    if onboarding_session is None:
        raise SearchJobWorkflowNotReadyError(
            "Search job workflow is not ready because no completed onboarding session exists."
        )

    context = build_search_job_context(onboarding_session=onboarding_session)
    source_sites = get_registered_parser_names()
    existing_run = await repository.get_latest_active_for_onboarding_session(
        onboarding_session_id=onboarding_session.id,
        monitoring_mode=monitoring_mode,
    )
    if existing_run is not None:
        logger.info(
            "search_job_workflow_reusing_active_run",
            workflow_run_id=existing_run.id,
            onboarding_session_id=existing_run.onboarding_session_id,
            user_id=existing_run.user_id,
            monitoring_mode=existing_run.monitoring_mode,
            status=existing_run.status,
        )
        return await _enqueue_existing_workflow_run(
            session=session,
            arq_redis=arq_redis,
            workflow_run=existing_run,
            parent_request_id=parent_request_id,
            monitoring_mode=monitoring_mode,
            subscription=subscription,
            access_pass=access_pass,
            monitoring_local_date=monitoring_local_date,
        )

    workflow_run = repository.add(
        user_id=user_id,
        onboarding_session_id=onboarding_session.id,
        search_strategy_summary=context.search_strategy_summary,
        hard_preferences=context.hard_preferences,
        soft_preferences=context.soft_preferences,
        source_sites=source_sites,
        monitoring_mode=monitoring_mode,
    )
    await session.flush()
    update_search_progress(
        repository=repository,
        workflow_run=workflow_run,
        event_type="phase_changed",
        internal_stage="queued",
        payload={"source_sites": source_sites},
    )
    await session.commit()
    await session.refresh(workflow_run)

    return await _enqueue_existing_workflow_run(
        session=session,
        arq_redis=arq_redis,
        workflow_run=workflow_run,
        parent_request_id=parent_request_id,
        monitoring_mode=monitoring_mode,
        subscription=subscription,
        access_pass=access_pass,
        monitoring_local_date=monitoring_local_date,
    )


async def _enqueue_existing_workflow_run(
    *,
    session: AsyncSession,
    arq_redis: ArqRedis,
    workflow_run: SearchJobWorkflowRun,
    parent_request_id: str | None,
    monitoring_mode: bool,
    subscription,
    access_pass,
    monitoring_local_date,
) -> SearchJobWorkflowRun:
    """Enqueue or re-enqueue an existing persisted workflow run."""
    repository = SearchJobWorkflowRunsRepository(session=session)

    try:
        job = await arq_redis.enqueue_job(
            "process_search_job_workflow",
            str(workflow_run.id),
            _job_id=str(workflow_run.id),
            _parent_request_id=parent_request_id,
            _user_id=workflow_run.user_id,
        )
        if job is None:
            logger.info(
                "search_job_workflow_reused_existing_job",
                workflow_run_id=workflow_run.id,
                onboarding_session_id=workflow_run.onboarding_session_id,
                user_id=workflow_run.user_id,
            )
            await _persist_monitoring_last_run_date(
                session=session,
                workflow_run=workflow_run,
                subscription=subscription,
                access_pass=access_pass,
                monitoring_local_date=monitoring_local_date,
                monitoring_mode=monitoring_mode,
            )
            return workflow_run
    except Exception as exc:
        workflow_run.status = "failed"
        workflow_run.error_message = "Failed to enqueue search-job workflow."
        update_search_progress(
            repository=repository,
            workflow_run=workflow_run,
            event_type="error",
            internal_stage="failed",
            payload={"error": "Failed to enqueue search-job workflow."},
        )
        await session.commit()
        logger.error(
            "search_job_workflow_enqueue_failed",
            workflow_run_id=workflow_run.id,
            user_id=workflow_run.user_id,
            error=str(exc),
            exc_info=True,
        )
        raise SearchJobWorkflowEnqueueError("Failed to enqueue search-job workflow.") from exc

    logger.info(
        "search_job_workflow_queued",
        workflow_run_id=workflow_run.id,
        onboarding_session_id=workflow_run.onboarding_session_id,
        user_id=workflow_run.user_id,
    )
    await _persist_monitoring_last_run_date(
        session=session,
        workflow_run=workflow_run,
        subscription=subscription,
        access_pass=access_pass,
        monitoring_local_date=monitoring_local_date,
        monitoring_mode=monitoring_mode,
    )
    return workflow_run


async def _persist_monitoring_last_run_date(
    *,
    session: AsyncSession,
    workflow_run: SearchJobWorkflowRun,
    subscription,
    access_pass,
    monitoring_local_date,
    monitoring_mode: bool,
) -> None:
    if not monitoring_mode or monitoring_local_date is None:
        return

    if subscription is None:
        subscription = BillingSubscriptionsRepository(session=session).add(
            user_id=workflow_run.user_id
        )
        subscription.plan_code = access_pass.pass_type if access_pass is not None else "pro"
        subscription.status = "inactive"
        if access_pass is not None:
            subscription.provider = access_pass.provider
            subscription.provider_transaction_id = access_pass.provider_transaction_id
            subscription.provider_price_id = access_pass.provider_price_id
            subscription.started_at = access_pass.starts_at
        await session.flush()

    if subscription.monitoring_last_run_local_date == monitoring_local_date:
        return

    subscription.monitoring_last_run_local_date = monitoring_local_date
    await session.commit()


async def _get_user_timezone(*, session: AsyncSession, user_id: str) -> str:
    try:
        parsed_user_id = UUID(user_id)
    except ValueError:
        return "UTC"

    user = await UsersRepository(session=session).get_by_id(user_id=parsed_user_id)
    if user is None:
        return "UTC"
    return user.timezone or "UTC"


def _monitoring_local_date(*, timezone: str, now: datetime | None = None):
    return (now or datetime.now(UTC)).astimezone(_safe_zoneinfo(timezone)).date()


def _monitoring_day_window_utc(*, local_date, timezone: str) -> tuple[datetime, datetime]:
    zone = _safe_zoneinfo(timezone)
    local_start = datetime.combine(local_date, time.min, tzinfo=zone)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def _safe_zoneinfo(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")
