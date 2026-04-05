from __future__ import annotations

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import get_logger
from src.modules.extraction.failures import build_enqueue_failure_details
from src.modules.extraction.models import ExtractionWorkflowRun
from src.modules.extraction.progress import update_extraction_progress
from src.modules.extraction.provider_health import ensure_cv_extraction_provider_available
from src.modules.extraction.repository import ExtractionWorkflowRunsRepository
from src.modules.extraction.use_cases.intake_cv import PreparedCvExtractionInput
from src.modules.onboarding.repository import OnboardingSessionsRepository

logger = get_logger("extraction.workflow_queue")


class WorkflowEnqueueError(RuntimeError):
    """Raised when an extraction workflow cannot be queued."""


def _supersede_onboarding_session(*, session_to_supersede, replacement_session_id) -> None:
    session_to_supersede.status = "superseded"
    session_to_supersede.superseded_by_session_id = replacement_session_id


async def queue_cv_extraction_workflow(
    *,
    session: AsyncSession,
    arq_redis: ArqRedis,
    user_id: str,
    prepared_cv: PreparedCvExtractionInput,
    parent_request_id: str | None = None,
) -> ExtractionWorkflowRun:
    """Persist and enqueue a workflow run for background processing."""
    await ensure_cv_extraction_provider_available(arq_redis=arq_redis)

    repository = ExtractionWorkflowRunsRepository(session=session)
    onboarding_repository = OnboardingSessionsRepository(session=session)
    active_sessions = await onboarding_repository.list_active_for_user(user_id=user_id)
    onboarding_session = active_sessions[0] if active_sessions else None

    if onboarding_session is None:
        onboarding_session = onboarding_repository.add(
            user_id=user_id,
            status="extracting",
            current_step="extraction",
        )
        await session.flush()
    elif onboarding_session.status == "draft":
        for stale_session in active_sessions[1:]:
            _supersede_onboarding_session(
                session_to_supersede=stale_session,
                replacement_session_id=onboarding_session.id,
            )
        onboarding_session.status = "extracting"
        onboarding_session.current_step = "extraction"
        onboarding_session.latest_workflow_run_id = None
        onboarding_session.extracted_profile = None
        onboarding_session.missing_info = None
        onboarding_session.preference_hints = None
        onboarding_session.clarification_turns = None
        onboarding_session.pending_user_prompt = None
        onboarding_session.pending_user_prompt_type = None
        onboarding_session.verification_score = None
        onboarding_session.verification_summary = None
        onboarding_session.search_strategy_summary = None
        onboarding_session.hard_preferences = None
        onboarding_session.soft_preferences = None
        onboarding_session.extraction_model = None
        onboarding_session.last_error_message = None
    else:
        for active_session in active_sessions:
            _supersede_onboarding_session(
                session_to_supersede=active_session,
                replacement_session_id=None,
            )
        await session.flush()
        replacement_session = onboarding_repository.add(
            user_id=user_id,
            status="extracting",
            current_step="extraction",
        )
        await session.flush()
        for active_session in active_sessions:
            active_session.superseded_by_session_id = replacement_session.id
        onboarding_session = replacement_session

    workflow_run = repository.add(
        user_id=user_id,
        onboarding_session_id=onboarding_session.id,
        status="queued",
        storage_bucket=prepared_cv.stored_object.bucket,
        storage_key=prepared_cv.stored_object.key,
        storage_uri=prepared_cv.stored_object.uri,
        cv_filename=prepared_cv.filename,
        cv_content_type=prepared_cv.content_type,
        cv_extension=prepared_cv.extension,
        cv_size_bytes=prepared_cv.size_bytes,
        cv_sha256=prepared_cv.sha256,
        extraction_strategy=prepared_cv.strategy,
        inline_text_characters=len(prepared_cv.inline_text) if prepared_cv.inline_text else None,
    )
    await session.flush()
    update_extraction_progress(
        repository=repository,
        workflow_run=workflow_run,
        event_type="phase_changed",
        phase="upload_received",
        payload={"storage_key": prepared_cv.stored_object.key},
    )
    onboarding_session.latest_workflow_run_id = workflow_run.id
    await session.commit()
    await session.refresh(workflow_run)

    try:
        job = await arq_redis.enqueue_job(
            "process_cv_extraction_workflow",
            str(workflow_run.id),
            _job_id=str(workflow_run.id),
            _parent_request_id=parent_request_id,
            _user_id=user_id,
        )
        if job is None:
            raise WorkflowEnqueueError("Workflow job already exists.")
    except Exception as exc:
        failure = build_enqueue_failure_details()
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
        onboarding_session.status = "failed"
        onboarding_session.current_step = "extraction"
        onboarding_session.last_error_message = failure.error_message
        await session.commit()
        logger.error(
            "cv_extraction_workflow_enqueue_failed",
            workflow_run_id=workflow_run.id,
            user_id=user_id,
            error=str(exc),
            exc_info=True,
        )
        raise WorkflowEnqueueError("Failed to enqueue extraction workflow.") from exc

    logger.info(
        "cv_extraction_workflow_queued",
        workflow_run_id=workflow_run.id,
        onboarding_session_id=onboarding_session.id,
        user_id=user_id,
        storage_key=prepared_cv.stored_object.key,
    )
    return workflow_run
