from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db_session
from src.extensions.arq.client import get_arq_redis
from src.extensions.gemini import GeminiIntegrationError
from src.modules.auth.dependencies import AuthContext, require_admin
from src.modules.search_jobs.presenters import build_search_job_workflow_run_response
from src.modules.search_jobs.schemas import (
    SearchJobWorkflowRunResponse,
    StartSearchJobWorkflowRequest,
)
from src.modules.search_jobs.use_cases.get_search_job_run import get_search_job_workflow_run
from src.modules.search_jobs.use_cases.queue_search_job_workflow import (
    SearchJobWorkflowEnqueueError,
    SearchJobWorkflowNotReadyError,
    queue_search_job_workflow,
)

router = APIRouter(prefix="/search-jobs", tags=["search-jobs"])
db_session_dependency = Depends(get_db_session)
arq_redis_dependency = Depends(get_arq_redis)
admin_dependency = Depends(require_admin)


@router.post(
    "/run",
    response_model=SearchJobWorkflowRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def queue_search_job_route(
    payload: StartSearchJobWorkflowRequest,
    request: Request,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> SearchJobWorkflowRunResponse:
    """Queue a background search-job workflow for a completed onboarding plan."""
    try:
        workflow_run = await queue_search_job_workflow(
            session=session,
            arq_redis=arq_redis,
            user_id=payload.user_id,
            monitoring_mode=payload.monitoring_mode,
            parent_request_id=getattr(request.state, "request_id", None),
        )
    except SearchJobWorkflowNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (SearchJobWorkflowEnqueueError, GeminiIntegrationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return build_search_job_workflow_run_response(workflow_run=workflow_run)


@router.get("/run/{workflow_run_id}", response_model=SearchJobWorkflowRunResponse)
async def get_search_job_run_route(
    workflow_run_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> SearchJobWorkflowRunResponse:
    """Return the current state of a search-job workflow run."""
    workflow_run = await get_search_job_workflow_run(
        session=session,
        workflow_run_id=workflow_run_id,
    )
    if workflow_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")

    return build_search_job_workflow_run_response(workflow_run=workflow_run)
