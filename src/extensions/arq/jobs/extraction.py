from __future__ import annotations

import inspect
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import with_session
from src.extensions.arq.middleware import arq_job_middleware
from src.logger import get_logger
from src.modules.extraction.failures import describe_extraction_failure
from src.modules.extraction.progress import update_extraction_progress
from src.modules.extraction.provider_health import (
    clear_cv_extraction_provider_failures,
    record_cv_extraction_provider_failure,
)
from src.modules.extraction.repository import ExtractionWorkflowRunsRepository
from src.modules.onboarding.repository import OnboardingSessionsRepository
from src.modules.onboarding.use_cases.advance_onboarding_flow import (
    _apply_graph_state_to_onboarding_session,
)
from src.workflows.search_setup.runtime import (
    get_search_setup_graph,
    get_search_setup_state,
    invoke_search_setup_graph,
)

logger = get_logger("arq.jobs.extraction")


@arq_job_middleware
@with_session
async def process_cv_extraction_workflow(
    ctx: dict,
    workflow_run_id: str,
    *,
    session: AsyncSession,
) -> None:
    """Run the extraction workflow in the background and persist the result."""
    arq_redis = ctx["redis"]
    repository = ExtractionWorkflowRunsRepository(session=session)
    onboarding_repository = OnboardingSessionsRepository(session=session)
    workflow_run = await repository.get_by_id(workflow_run_id=UUID(workflow_run_id))
    if workflow_run is None:
        raise RuntimeError(f"Extraction workflow run not found: {workflow_run_id}")
    onboarding_session = None
    if workflow_run.onboarding_session_id:
        onboarding_session = await onboarding_repository.get_by_id(
            onboarding_session_id=workflow_run.onboarding_session_id
        )

    workflow_run.status = "extracting"
    workflow_run.error_message = None
    update_extraction_progress(
        repository=repository,
        workflow_run=workflow_run,
        event_type="phase_changed",
        phase="file_stored",
    )
    if onboarding_session is not None:
        onboarding_session.status = "extracting"
        onboarding_session.current_step = "extraction"
        onboarding_session.last_error_message = None
    await session.commit()

    try:
        update_extraction_progress(
            repository=repository,
            workflow_run=workflow_run,
            event_type="step_started",
            phase="text_extraction",
        )
        graph = get_search_setup_graph()
        if inspect.isawaitable(graph):
            await graph
        thread_id = str(onboarding_session.id) if onboarding_session else str(workflow_run.id)
        config = {"configurable": {"thread_id": thread_id}}
        result = await invoke_search_setup_graph(
            graph_input={
                "messages": [],
                "status": "ingesting",
                "user_id": workflow_run.user_id,
                "onboarding_session_id": str(onboarding_session.id) if onboarding_session else "",
                "cv_object_key": workflow_run.storage_key,
                "cv_object_uri": getattr(workflow_run, "storage_uri", ""),
                "cv_filename": workflow_run.cv_filename,
                "cv_content_type": workflow_run.cv_content_type,
                "cv_extension": workflow_run.cv_extension,
                "extraction_strategy": workflow_run.extraction_strategy,
                "clarification_turns": [],
                "clarification_cycle_start_index": 0,
                "verification_retry_count": 0,
            },
            config=config,
            durability="sync",
        )
        update_extraction_progress(
            repository=repository,
            workflow_run=workflow_run,
            event_type="step_completed",
            phase="cv_analysis",
        )
        update_extraction_progress(
            repository=repository,
            workflow_run=workflow_run,
            event_type="phase_changed",
            phase="building_profile",
        )
        snapshot = await get_search_setup_state(config)
        values = snapshot.values or {}
    except Exception as exc:
        failure = describe_extraction_failure(exc=exc)
        workflow_run.status = "failed"
        workflow_run.error_message = failure.error_message
        update_extraction_progress(
            repository=repository,
            workflow_run=workflow_run,
            event_type="error",
            phase="failed",
            payload={
                "error_code": failure.error_code,
                "retryable": failure.retryable,
                "error_message": failure.error_message,
                "ui_label": failure.ui_label,
                "ui_description": failure.ui_description,
            },
        )
        if onboarding_session is not None:
            onboarding_session.status = "failed"
            onboarding_session.current_step = "extraction"
            onboarding_session.last_error_message = failure.error_message
        await session.commit()
        try:
            await record_cv_extraction_provider_failure(
                arq_redis=arq_redis,
                error_code=failure.error_code,
            )
        except Exception:
            logger.warning(
                "cv_extraction_provider_failure_record_failed",
                workflow_run_id=workflow_run.id,
                error_code=failure.error_code,
                exc_info=True,
            )
        logger.error(
            "cv_extraction_workflow_failed",
            workflow_run_id=workflow_run.id,
            user_id=workflow_run.user_id,
            error_code=failure.error_code,
            error=str(exc),
            exc_info=True,
        )
        raise

    workflow_run.extracted_profile = values.get("extracted_profile")
    workflow_run.missing_info = values.get("missing_info", [])
    workflow_run.preference_hints = values.get("preference_hints", [])
    workflow_run.extraction_model = values.get("extraction_model")
    workflow_run.error_message = None
    update_extraction_progress(
        repository=repository,
        workflow_run=workflow_run,
        event_type="phase_changed",
        phase="ready_for_questions",
        payload={"status": values.get("status", workflow_run.status)},
    )
    if onboarding_session is not None:
        onboarding_session.latest_workflow_run_id = workflow_run.id
        onboarding_session.extracted_profile = values.get("extracted_profile")
        onboarding_session.extraction_model = values.get("extraction_model")
        _apply_graph_state_to_onboarding_session(
            onboarding_session=onboarding_session,
            graph_result=result,
            graph_values=values,
        )
        workflow_run.status = onboarding_session.status
    else:
        workflow_run.status = values.get("status", workflow_run.status)
    await session.commit()
    try:
        await clear_cv_extraction_provider_failures(arq_redis=arq_redis)
    except Exception:
        logger.warning(
            "cv_extraction_provider_failure_clear_failed",
            workflow_run_id=workflow_run.id,
            exc_info=True,
        )

    logger.info(
        "cv_extraction_workflow_persisted",
        workflow_run_id=workflow_run.id,
        onboarding_session_id=workflow_run.onboarding_session_id,
        user_id=workflow_run.user_id,
        status=workflow_run.status,
    )
