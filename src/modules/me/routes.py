from __future__ import annotations

from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import get_db_session
from src.extensions.arq.client import get_arq_redis
from src.extensions.gemini import GeminiIntegrationError
from src.extensions.s3 import S3StorageError
from src.modules.auth.dependencies import AuthContext, require_authenticated_user
from src.modules.extraction.routes import _build_workflow_run_response as build_extraction_response
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
from src.modules.onboarding.routes import _advance_onboarding_flow, _resume_onboarding_flow
from src.modules.onboarding.schemas import OnboardingSessionResponse, SubmitOnboardingAnswerRequest
from src.modules.onboarding.use_cases.get_active_onboarding_session import (
    get_active_onboarding_session,
)
from src.modules.search_jobs.routes import _build_workflow_run_response as build_search_job_response
from src.modules.search_jobs.schemas import SearchJobWorkflowRunResponse
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


@router.get("", response_model=UserResponse)
async def get_me_route(
    context: AuthContext = user_auth_dependency,
) -> UserResponse:
    return UserResponse.model_validate(context.user)


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


@router.post("/onboarding/respond", response_model=OnboardingSessionResponse)
async def respond_my_onboarding_route(
    payload: SubmitOnboardingAnswerRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> OnboardingSessionResponse:
    return await _resume_onboarding_flow(
        user_id=str(context.user.id),
        payload=payload,
        session=session,
        arq_redis=arq_redis,
    )


@router.post("/extraction/cv/run", status_code=status.HTTP_202_ACCEPTED)
async def run_my_extraction_route(
    request: Request,
    file: UploadFile = upload_file_field,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
):
    try:
        prepared_cv = await intake_cv_for_extraction(upload=file)
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
    return build_extraction_response(workflow_run=workflow_run)


@router.get("/extraction/runs/{workflow_run_id}")
async def get_my_extraction_run_route(
    workflow_run_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
):
    workflow_run = await get_cv_extraction_workflow_run(
        session=session, workflow_run_id=workflow_run_id
    )
    if workflow_run is None or workflow_run.user_id != str(context.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    return build_extraction_response(workflow_run=workflow_run)


@router.post(
    "/search-jobs/run",
    response_model=SearchJobWorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_my_search_jobs_route(
    request: Request,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> SearchJobWorkflowRunResponse:
    try:
        workflow_run = await queue_search_job_workflow(
            session=session,
            arq_redis=arq_redis,
            user_id=str(context.user.id),
            parent_request_id=getattr(request.state, "request_id", None),
        )
    except SearchJobWorkflowNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (SearchJobWorkflowEnqueueError, GeminiIntegrationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return build_search_job_response(workflow_run=workflow_run)


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
    return build_search_job_response(workflow_run=workflow_run)
