from __future__ import annotations

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import get_logger
from src.modules.billing.repository import BillingSubscriptionsRepository
from src.modules.billing.service import build_billing_entitlements
from src.modules.onboarding.repository import OnboardingSessionsRepository
from src.modules.search_jobs.models import SearchJobWorkflowRun
from src.modules.search_jobs.progress import update_search_progress
from src.modules.search_jobs.repository import SearchJobWorkflowRunsRepository
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
    if monitoring_mode:
        subscription = await BillingSubscriptionsRepository(session=session).get_by_user_id(
            user_id=user_id
        )
        entitlements = build_billing_entitlements(subscription=subscription)
        if not entitlements.can_use_daily_monitoring:
            raise SearchJobMonitoringNotAllowedError(
                "Daily monitoring is available on Vitable Pro."
            )

    onboarding_repository = OnboardingSessionsRepository(session=session)
    onboarding_session = await onboarding_repository.get_latest_completed_for_user(user_id=user_id)
    if onboarding_session is None:
        raise SearchJobWorkflowNotReadyError(
            "Search job workflow is not ready because no completed onboarding session exists."
        )

    context = build_search_job_context(onboarding_session=onboarding_session)
    source_sites = get_registered_parser_names()
    repository = SearchJobWorkflowRunsRepository(session=session)
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
    )


async def _enqueue_existing_workflow_run(
    *,
    session: AsyncSession,
    arq_redis: ArqRedis,
    workflow_run: SearchJobWorkflowRun,
    parent_request_id: str | None,
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
    return workflow_run
