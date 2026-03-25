from __future__ import annotations

import asyncio
import json
from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import get_db_session
from src.extensions.arq.client import get_arq_redis
from src.extensions.gemini import GeminiIntegrationError
from src.extensions.s3 import S3StorageError
from src.modules.auth.dependencies import AuthContext, require_authenticated_user
from src.modules.extraction.repository import ExtractionWorkflowRunsRepository
from src.modules.extraction.routes import _build_workflow_run_response as build_extraction_response
from src.modules.extraction.schemas import (
    CvExtractionWorkflowRunResponse,
    ExtractionProgressEventResponse,
)
from src.modules.extraction.use_cases.get_cv_extraction_run import get_cv_extraction_workflow_run
from src.modules.extraction.use_cases.intake_cv import (
    CvFileTooLargeError,
    InvalidCvFileError,
    UnsupportedCvFileError,
    intake_cv_for_extraction,
)
from src.modules.extraction.use_cases.queue_cv_extraction import (
    WorkflowEnqueueError,
    queue_cv_extraction_workflow,
)
from src.modules.job_tracker.repository import TrackedJobsRepository
from src.modules.job_tracker.schemas import JobTrackerListQuery
from src.modules.job_tracker.service import normalize_job_url
from src.modules.me.frontend_state import build_app_state_snapshot, build_onboarding_thread
from src.modules.me.schemas import MeAppStateResponse
from src.modules.onboarding.routes import _advance_onboarding_flow, _resume_onboarding_flow
from src.modules.onboarding.schemas import (
    OnboardingRespondResponse,
    OnboardingSessionResponse,
    OnboardingThreadResponse,
    SubmitOnboardingAnswerRequest,
)
from src.modules.onboarding.use_cases.get_active_onboarding_session import (
    get_active_onboarding_session,
)
from src.modules.search_jobs.repository import SearchJobWorkflowRunsRepository
from src.modules.search_jobs.routes import _build_workflow_run_response as build_search_job_response
from src.modules.search_jobs.schemas import (
    SearchJobProgressEventResponse,
    SearchJobWorkflowRunResponse,
)
from src.modules.search_jobs.use_cases.get_search_job_run import get_search_job_workflow_run
from src.modules.search_jobs.use_cases.queue_search_job_workflow import (
    SearchJobWorkflowEnqueueError,
    SearchJobWorkflowNotReadyError,
    queue_search_job_workflow,
)
from src.modules.users.schemas import UserResponse

router = APIRouter(prefix="/me", tags=["me"])
user_auth_dependency = Depends(require_authenticated_user)
db_session_dependency = Depends(get_db_session)
arq_redis_dependency = Depends(get_arq_redis)
upload_file_field = File(...)


def _sse_event(*, event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _build_user_search_job_response(
    *,
    session: AsyncSession,
    user_id: str,
    workflow_run,
) -> SearchJobWorkflowRunResponse:
    response = build_search_job_response(workflow_run=workflow_run)
    repository = TrackedJobsRepository(session=session)
    tracked_jobs = await repository.list_jobs_for_user(
        user_id=user_id,
        query=JobTrackerListQuery(archived=False),
    )
    saved_by_url = {
        job.source_job_url: job
        for job in tracked_jobs
        if job.source_job_url and job.archived_at is None
    }
    enriched_jobs = []
    for job in response.jobs:
        normalized_job_url = normalize_job_url(job.job_url) or ""
        tracked_job = saved_by_url.get(normalized_job_url)
        site_display_name = {
            "indeed": "Indeed",
            "hh": "HH",
            "habr_career": "Habr Career",
            "getonbrd": "Get on Board",
            "computrabajo": "Computrabajo",
            "linkedin": "LinkedIn",
        }.get(job.site, job.site.title() if job.site else None)
        enriched_jobs.append(
            job.model_copy(
                update={
                    "is_saved_to_tracker": tracked_job is not None,
                    "tracked_job_id": str(tracked_job.id) if tracked_job is not None else None,
                    "site_display_name": site_display_name,
                    "site_logo_key": job.site,
                    "display_badge_label": job.fit_level.title() if job.fit_level else None,
                }
            )
        )
    return response.model_copy(update={"jobs": enriched_jobs})


@router.get("", response_model=UserResponse)
async def get_me_route(
    context: AuthContext = user_auth_dependency,
) -> UserResponse:
    return UserResponse.model_validate(context.user)


@router.get("/app-state", response_model=MeAppStateResponse)
async def get_my_app_state_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> MeAppStateResponse:
    snapshot = await build_app_state_snapshot(session=session, user=context.user)
    return MeAppStateResponse(**snapshot.__dict__)


@router.get("/onboarding/active", response_model=OnboardingSessionResponse)
async def get_my_onboarding_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> OnboardingSessionResponse:
    onboarding_session = await get_active_onboarding_session(
        session=session, user_id=str(context.user.id)
    )
    if onboarding_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Active onboarding session not found."
        )
    return OnboardingSessionResponse.model_validate(onboarding_session)


@router.post(
    "/onboarding/restart",
    response_model=OnboardingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def restart_my_onboarding_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> OnboardingSessionResponse:
    from src.modules.onboarding.use_cases.restart_onboarding_session import (
        restart_onboarding_session,
    )

    onboarding_session = await restart_onboarding_session(
        session=session, user_id=str(context.user.id)
    )
    return OnboardingSessionResponse.model_validate(onboarding_session)


@router.post("/onboarding/run", response_model=OnboardingSessionResponse)
async def run_my_onboarding_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> OnboardingSessionResponse:
    return await _advance_onboarding_flow(user_id=str(context.user.id), session=session)


@router.get("/onboarding/thread", response_model=OnboardingThreadResponse)
async def get_my_onboarding_thread_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> OnboardingThreadResponse:
    onboarding_session = await get_active_onboarding_session(
        session=session, user_id=str(context.user.id)
    )
    if onboarding_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Active onboarding session not found."
        )
    latest_search_job_run = await SearchJobWorkflowRunsRepository(
        session=session
    ).get_latest_for_user(user_id=str(context.user.id))
    return build_onboarding_thread(
        onboarding_session=onboarding_session,
        search_job_workflow_run_id=latest_search_job_run.id if latest_search_job_run else None,
    )


@router.post("/onboarding/respond", response_model=OnboardingRespondResponse)
async def respond_my_onboarding_route(
    payload: SubmitOnboardingAnswerRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> OnboardingRespondResponse:
    onboarding_session = await _resume_onboarding_flow(
        user_id=str(context.user.id),
        payload=payload,
        session=session,
        arq_redis=arq_redis,
    )
    latest_search_job_run = await SearchJobWorkflowRunsRepository(
        session=session
    ).get_latest_for_user(user_id=str(context.user.id))
    search_job_run_id = (
        latest_search_job_run.id
        if latest_search_job_run is not None
        and latest_search_job_run.onboarding_session_id == onboarding_session.id
        else None
    )
    return OnboardingRespondResponse(
        session=OnboardingSessionResponse.model_validate(onboarding_session),
        thread=build_onboarding_thread(
            onboarding_session=onboarding_session,
            search_job_workflow_run_id=search_job_run_id,
        ),
        onboarding_completed=onboarding_session.status == "completed",
        search_job_enqueued=search_job_run_id is not None,
        search_job_workflow_run_id=search_job_run_id,
    )


@router.post(
    "/extraction/cv/run",
    response_model=CvExtractionWorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_my_extraction_route(
    request: Request,
    file: UploadFile = upload_file_field,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> CvExtractionWorkflowRunResponse:
    try:
        prepared_cv = await intake_cv_for_extraction(upload=file)
        # The authenticated request may already hold a DB connection from auth/session lookups.
        # Release it after long-running upload/storage I/O before we start a write transaction.
        await session.rollback()
        workflow_run = await queue_cv_extraction_workflow(
            session=session,
            arq_redis=arq_redis,
            user_id=str(context.user.id),
            prepared_cv=prepared_cv,
            parent_request_id=getattr(request.state, "request_id", None),
        )
    except CvFileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except UnsupportedCvFileError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except InvalidCvFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (S3StorageError, GeminiIntegrationError, WorkflowEnqueueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is temporarily unavailable.",
        ) from exc
    return build_extraction_response(workflow_run=workflow_run)


@router.get("/extraction/runs/{workflow_run_id}")
async def get_my_extraction_run_route(
    workflow_run_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> CvExtractionWorkflowRunResponse:
    workflow_run = await get_cv_extraction_workflow_run(
        session=session, workflow_run_id=workflow_run_id
    )
    if workflow_run is None or workflow_run.user_id != str(context.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    return build_extraction_response(workflow_run=workflow_run)


@router.get(
    "/extraction/runs/{workflow_run_id}/events",
    response_class=StreamingResponse,
)
async def stream_my_extraction_run_events_route(
    workflow_run_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> StreamingResponse:
    repository = ExtractionWorkflowRunsRepository(session=session)
    workflow_run = await repository.get_by_id(workflow_run_id=workflow_run_id)
    if workflow_run is None or workflow_run.user_id != str(context.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")

    async def event_stream():
        last_seen = None
        while True:
            events = await repository.list_progress_events_after(
                workflow_run_id=workflow_run_id,
                created_after=last_seen,
            )
            for item in events:
                last_seen = item.created_at
                payload = ExtractionProgressEventResponse(
                    workflow_run_id=item.workflow_run_id,
                    event_type=item.event_type,
                    ui_phase=item.ui_phase,
                    ui_label=item.ui_label,
                    ui_description=item.ui_description,
                    progress_percent=item.progress_percent,
                    progress_stage_index=item.progress_stage_index,
                    progress_stage_total=item.progress_stage_total,
                    payload=item.payload,
                    created_at=item.created_at,
                )
                yield _sse_event(event=item.event_type, data=payload.model_dump(mode="json"))
            workflow_run_latest = await repository.get_by_id(workflow_run_id=workflow_run_id)
            if workflow_run_latest is None or workflow_run_latest.status in {"completed", "failed"}:
                terminal = (
                    build_extraction_response(workflow_run=workflow_run_latest)
                    if workflow_run_latest
                    else None
                )
                yield _sse_event(
                    event="terminal",
                    data=(
                        terminal.model_dump(mode="json")
                        if terminal is not None
                        else {"status": "missing"}
                    ),
                )
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post(
    "/search-jobs/run",
    response_model=SearchJobWorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_my_search_jobs_route(
    request: Request,
    monitoring_mode: bool = False,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> SearchJobWorkflowRunResponse:
    try:
        workflow_run = await queue_search_job_workflow(
            session=session,
            arq_redis=arq_redis,
            user_id=str(context.user.id),
            monitoring_mode=monitoring_mode,
            parent_request_id=getattr(request.state, "request_id", None),
        )
    except SearchJobWorkflowNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (SearchJobWorkflowEnqueueError, GeminiIntegrationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return await _build_user_search_job_response(
        session=session,
        user_id=str(context.user.id),
        workflow_run=workflow_run,
    )


@router.get("/search-jobs/runs/{workflow_run_id}", response_model=SearchJobWorkflowRunResponse)
async def get_my_search_job_run_route(
    workflow_run_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> SearchJobWorkflowRunResponse:
    workflow_run = await get_search_job_workflow_run(
        session=session, workflow_run_id=workflow_run_id
    )
    if workflow_run is None or workflow_run.user_id != str(context.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    return await _build_user_search_job_response(
        session=session,
        user_id=str(context.user.id),
        workflow_run=workflow_run,
    )


@router.get(
    "/search-jobs/runs/{workflow_run_id}/progress",
    response_model=list[SearchJobProgressEventResponse],
)
async def get_my_search_job_progress_route(
    workflow_run_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[SearchJobProgressEventResponse]:
    repository = SearchJobWorkflowRunsRepository(session=session)
    workflow_run = await repository.get_by_id(workflow_run_id=workflow_run_id)
    if workflow_run is None or workflow_run.user_id != str(context.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    events = await repository.list_progress_events(workflow_run_id=workflow_run_id)
    return [
        SearchJobProgressEventResponse(
            workflow_run_id=item.workflow_run_id,
            event_type=item.event_type,
            internal_stage=item.internal_stage,
            display_stage=item.display_stage,
            display_label=item.display_label,
            display_description=item.display_description,
            site=item.site,
            progress_order=item.progress_order,
            display_icon_key=item.display_icon_key,
            display_color_key=item.display_color_key,
            site_display_name=item.site_display_name,
            payload=item.payload,
            created_at=item.created_at,
        )
        for item in events
    ]


@router.get(
    "/search-jobs/runs/{workflow_run_id}/events",
    response_class=StreamingResponse,
)
async def stream_my_search_job_progress_route(
    workflow_run_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> StreamingResponse:
    repository = SearchJobWorkflowRunsRepository(session=session)
    workflow_run = await repository.get_by_id(workflow_run_id=workflow_run_id)
    if workflow_run is None or workflow_run.user_id != str(context.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")

    async def event_stream():
        last_seen = None
        while True:
            events = await repository.list_progress_events_after(
                workflow_run_id=workflow_run_id,
                created_after=last_seen,
            )
            for item in events:
                last_seen = item.created_at
                payload = SearchJobProgressEventResponse(
                    workflow_run_id=item.workflow_run_id,
                    event_type=item.event_type,
                    internal_stage=item.internal_stage,
                    display_stage=item.display_stage,
                    display_label=item.display_label,
                    display_description=item.display_description,
                    site=item.site,
                    progress_order=item.progress_order,
                    display_icon_key=item.display_icon_key,
                    display_color_key=item.display_color_key,
                    site_display_name=item.site_display_name,
                    payload=item.payload,
                    created_at=item.created_at,
                )
                yield _sse_event(event=item.event_type, data=payload.model_dump(mode="json"))
            workflow_run_latest = await repository.get_by_id(workflow_run_id=workflow_run_id)
            if workflow_run_latest is None or workflow_run_latest.status in {"completed", "failed"}:
                terminal_payload = (
                    (
                        await _build_user_search_job_response(
                            session=session,
                            user_id=str(context.user.id),
                            workflow_run=workflow_run_latest,
                        )
                    )
                    if workflow_run_latest is not None
                    else {"status": "missing"}
                )
                data = (
                    terminal_payload.model_dump(mode="json")
                    if hasattr(terminal_payload, "model_dump")
                    else terminal_payload
                )
                yield _sse_event(event="terminal", data=data)
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
