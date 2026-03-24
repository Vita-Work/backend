from __future__ import annotations

from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import get_db_session
from src.extensions.arq.client import get_arq_redis
from src.extensions.gemini import GeminiIntegrationError
from src.extensions.s3 import S3StorageError
from src.modules.auth.dependencies import AuthContext, require_admin
from src.modules.extraction.repository import ExtractionWorkflowRunsRepository
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
from src.modules.onboarding.repository import OnboardingSessionsRepository
from src.modules.onboarding.schemas import OnboardingSessionResponse
from src.modules.onboarding.use_cases.restart_onboarding_session import restart_onboarding_session
from src.modules.search_jobs.repository import SearchJobWorkflowRunsRepository
from src.modules.search_jobs.routes import _build_workflow_run_response as build_search_job_response
from src.modules.search_jobs.schemas import SearchJobWorkflowRunResponse
from src.modules.search_jobs.use_cases.get_search_job_run import get_search_job_workflow_run
from src.modules.search_jobs.use_cases.queue_search_job_workflow import (
    SearchJobWorkflowEnqueueError,
    SearchJobWorkflowNotReadyError,
    queue_search_job_workflow,
)
from src.modules.users.repository import UsersRepository
from src.modules.users.schemas import CreateUserRequest, UserResponse
from src.modules.users.use_cases.create_user import UserEmailAlreadyExistsError, create_user

router = APIRouter(prefix="/admin", tags=["admin"])
admin_dependency = Depends(require_admin)
db_session_dependency = Depends(get_db_session)
arq_redis_dependency = Depends(get_arq_redis)
upload_file_field = File(...)


class AdminUpdateUserRequest(BaseModel):
    full_name: str | None = None
    timezone: str | None = None
    locale: str | None = None
    status: str | None = None


@router.get("/users", response_model=list[UserResponse])
async def list_users_route(
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[UserResponse]:
    users = await UsersRepository(session=session).list_all()
    return [UserResponse.model_validate(user) for user in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_admin_route(
    user_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> UserResponse:
    user = await UsersRepository(session=session).get_by_id(user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserResponse.model_validate(user)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_admin_route(
    payload: CreateUserRequest,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> UserResponse:
    try:
        user = await create_user(
            session=session,
            email=payload.email,
            full_name=payload.full_name,
            timezone=payload.timezone,
            locale=payload.locale,
        )
    except UserEmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists."
        ) from exc
    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user_admin_route(
    user_id: UUID,
    payload: AdminUpdateUserRequest,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> UserResponse:
    users_repository = UsersRepository(session=session)
    user = await users_repository.get_by_id(user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() if payload.full_name else None
    if payload.timezone is not None:
        user.timezone = payload.timezone.strip() or "UTC"
    if payload.locale is not None:
        user.locale = payload.locale.strip() if payload.locale else None
    if payload.status is not None:
        user.status = payload.status
    await session.commit()
    await session.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/disable", response_model=UserResponse)
async def disable_user_admin_route(
    user_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> UserResponse:
    user = await UsersRepository(session=session).get_by_id(user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.status = "disabled"
    await session.commit()
    await session.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/enable", response_model=UserResponse)
async def enable_user_admin_route(
    user_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> UserResponse:
    user = await UsersRepository(session=session).get_by_id(user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.status = "active"
    await session.commit()
    await session.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", response_model=UserResponse)
async def delete_user_admin_route(
    user_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> UserResponse:
    user = await UsersRepository(session=session).get_by_id(user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    user.status = "deleted"
    await session.commit()
    await session.refresh(user)
    return UserResponse.model_validate(user)


@router.get("/onboarding-sessions", response_model=list[OnboardingSessionResponse])
async def list_onboarding_sessions_admin_route(
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[OnboardingSessionResponse]:
    sessions = await OnboardingSessionsRepository(session=session).list_all()
    return [OnboardingSessionResponse.model_validate(item) for item in sessions]


@router.get("/onboarding-sessions/{session_id}", response_model=OnboardingSessionResponse)
async def get_onboarding_session_admin_route(
    session_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> OnboardingSessionResponse:
    onboarding_session = await OnboardingSessionsRepository(session=session).get_by_id(
        onboarding_session_id=session_id
    )
    if onboarding_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding session not found."
        )
    return OnboardingSessionResponse.model_validate(onboarding_session)


@router.delete("/onboarding-sessions/{session_id}", response_model=OnboardingSessionResponse)
async def delete_onboarding_session_admin_route(
    session_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> OnboardingSessionResponse:
    repository = OnboardingSessionsRepository(session=session)
    onboarding_session = await repository.get_by_id(onboarding_session_id=session_id)
    if onboarding_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Onboarding session not found."
        )
    onboarding_session.status = "deleted"
    onboarding_session.pending_user_prompt = None
    onboarding_session.pending_user_prompt_type = None
    await session.commit()
    await session.refresh(onboarding_session)
    return OnboardingSessionResponse.model_validate(onboarding_session)


@router.post(
    "/users/{user_id}/onboarding/restart",
    response_model=OnboardingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def restart_user_onboarding_admin_route(
    user_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> OnboardingSessionResponse:
    onboarding_session = await restart_onboarding_session(session=session, user_id=str(user_id))
    return OnboardingSessionResponse.model_validate(onboarding_session)


@router.get("/extraction-runs")
async def list_extraction_runs_admin_route(
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
):
    runs = await ExtractionWorkflowRunsRepository(session=session).list_all()
    return [build_extraction_response(workflow_run=run) for run in runs]


@router.get("/extraction-runs/{workflow_run_id}")
async def get_extraction_run_admin_route(
    workflow_run_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
):
    workflow_run = await get_cv_extraction_workflow_run(
        session=session, workflow_run_id=workflow_run_id
    )
    if workflow_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    return build_extraction_response(workflow_run=workflow_run)


@router.delete("/extraction-runs/{workflow_run_id}")
async def delete_extraction_run_admin_route(
    workflow_run_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
):
    repository = ExtractionWorkflowRunsRepository(session=session)
    workflow_run = await repository.get_by_id(workflow_run_id=workflow_run_id)
    if workflow_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    workflow_run.status = "deleted"
    await session.commit()
    return build_extraction_response(workflow_run=workflow_run)


@router.post("/users/{user_id}/extraction/run", status_code=status.HTTP_202_ACCEPTED)
async def run_extraction_for_user_admin_route(
    user_id: UUID,
    request: Request,
    file: UploadFile = upload_file_field,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
):
    try:
        prepared_cv = await intake_cv_for_extraction(upload=file)
        workflow_run = await queue_cv_extraction_workflow(
            session=session,
            arq_redis=arq_redis,
            user_id=str(user_id),
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


@router.get("/search-job-runs", response_model=list[SearchJobWorkflowRunResponse])
async def list_search_job_runs_admin_route(
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[SearchJobWorkflowRunResponse]:
    runs = await SearchJobWorkflowRunsRepository(session=session).list_all()
    return [build_search_job_response(workflow_run=run) for run in runs]


@router.get("/search-job-runs/{workflow_run_id}", response_model=SearchJobWorkflowRunResponse)
async def get_search_job_run_admin_route(
    workflow_run_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> SearchJobWorkflowRunResponse:
    workflow_run = await get_search_job_workflow_run(
        session=session, workflow_run_id=workflow_run_id
    )
    if workflow_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    return build_search_job_response(workflow_run=workflow_run)


@router.delete("/search-job-runs/{workflow_run_id}", response_model=SearchJobWorkflowRunResponse)
async def delete_search_job_run_admin_route(
    workflow_run_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> SearchJobWorkflowRunResponse:
    repository = SearchJobWorkflowRunsRepository(session=session)
    workflow_run = await repository.get_by_id(workflow_run_id=workflow_run_id)
    if workflow_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    workflow_run.status = "deleted"
    await session.commit()
    return build_search_job_response(workflow_run=workflow_run)


@router.post(
    "/users/{user_id}/search-jobs/run",
    response_model=SearchJobWorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_search_jobs_for_user_admin_route(
    user_id: UUID,
    request: Request,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> SearchJobWorkflowRunResponse:
    try:
        workflow_run = await queue_search_job_workflow(
            session=session,
            arq_redis=arq_redis,
            user_id=str(user_id),
            parent_request_id=getattr(request.state, "request_id", None),
        )
    except SearchJobWorkflowNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (SearchJobWorkflowEnqueueError, GeminiIntegrationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return build_search_job_response(workflow_run=workflow_run)
