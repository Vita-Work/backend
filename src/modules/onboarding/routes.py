from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db_session
from src.extensions.arq.client import get_arq_redis
from src.modules.auth.dependencies import AuthContext, require_admin
from src.modules.onboarding.schemas import (
    OnboardingSessionResponse,
    SubmitOnboardingAnswerRequest,
)
from src.modules.onboarding.use_cases.advance_onboarding_flow import (
    ActiveOnboardingSessionNotFoundError,
    OnboardingFlowNotReadyError,
    advance_onboarding_flow,
)
from src.modules.onboarding.use_cases.get_active_onboarding_session import (
    get_active_onboarding_session,
)
from src.modules.onboarding.use_cases.restart_onboarding_session import (
    restart_onboarding_session,
)
from src.modules.search_jobs.use_cases.queue_search_job_workflow import (
    SearchJobWorkflowEnqueueError,
    SearchJobWorkflowNotReadyError,
    queue_search_job_workflow,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
db_session_dependency = Depends(get_db_session)
arq_redis_dependency = Depends(get_arq_redis)
admin_dependency = Depends(require_admin)


@router.get("/users/{user_id}/active", response_model=OnboardingSessionResponse)
async def get_active_onboarding_session_route(
    user_id: str,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> OnboardingSessionResponse:
    """Return the active onboarding session for a user."""
    onboarding_session = await get_active_onboarding_session(
        session=session,
        user_id=user_id,
    )
    if onboarding_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active onboarding session not found.",
        )

    return OnboardingSessionResponse.model_validate(onboarding_session)


@router.post(
    "/users/{user_id}/restart",
    response_model=OnboardingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def restart_onboarding_session_route(
    user_id: str,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> OnboardingSessionResponse:
    """Supersede the current onboarding flow and create a fresh draft session."""
    onboarding_session = await restart_onboarding_session(
        session=session,
        user_id=user_id,
    )
    return OnboardingSessionResponse.model_validate(onboarding_session)


async def _advance_onboarding_flow(
    user_id: str,
    session: AsyncSession = db_session_dependency,
) -> OnboardingSessionResponse:
    """Advance onboarding until the next prompt or completion."""
    try:
        onboarding_session = await advance_onboarding_flow(
            session=session,
            user_id=user_id,
        )
    except ActiveOnboardingSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except OnboardingFlowNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return OnboardingSessionResponse.model_validate(onboarding_session)


async def _resume_onboarding_flow(
    user_id: str,
    payload: SubmitOnboardingAnswerRequest,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> OnboardingSessionResponse:
    """Resume onboarding with the user's latest answer."""
    try:
        onboarding_session = await advance_onboarding_flow(
            session=session,
            user_id=user_id,
            answer=payload.answer,
        )
    except ActiveOnboardingSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except OnboardingFlowNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if onboarding_session.status == "completed":
        try:
            await queue_search_job_workflow(
                session=session,
                arq_redis=arq_redis,
                user_id=user_id,
            )
        except (SearchJobWorkflowEnqueueError, SearchJobWorkflowNotReadyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    return OnboardingSessionResponse.model_validate(onboarding_session)


@router.post("/users/{user_id}/run", response_model=OnboardingSessionResponse)
async def run_onboarding_flow_route(
    user_id: str,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> OnboardingSessionResponse:
    """Advance the active onboarding flow until the next human prompt or completion."""
    return await _advance_onboarding_flow(user_id=user_id, session=session)


@router.post("/users/{user_id}/respond", response_model=OnboardingSessionResponse)
async def respond_to_onboarding_prompt_route(
    user_id: str,
    payload: SubmitOnboardingAnswerRequest,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> OnboardingSessionResponse:
    """Resume the active onboarding flow with the user's latest answer."""
    return await _resume_onboarding_flow(
        user_id=user_id,
        payload=payload,
        session=session,
        arq_redis=arq_redis,
    )
