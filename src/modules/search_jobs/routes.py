from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db_session
from src.extensions.arq.client import get_arq_redis
from src.extensions.gemini import GeminiIntegrationError
from src.modules.auth.dependencies import AuthContext, require_admin
from src.modules.search_jobs.models import SearchJobWorkflowRun
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
from src.workflows.search_job.schemas import SiteAgentResult, UnifiedJob

router = APIRouter(prefix="/search-jobs", tags=["search-jobs"])
db_session_dependency = Depends(get_db_session)
arq_redis_dependency = Depends(get_arq_redis)
admin_dependency = Depends(require_admin)


def _build_workflow_run_response(
    *,
    workflow_run: SearchJobWorkflowRun,
) -> SearchJobWorkflowRunResponse:
    return SearchJobWorkflowRunResponse(
        workflow_run_id=workflow_run.id,
        onboarding_session_id=workflow_run.onboarding_session_id,
        user_id=workflow_run.user_id,
        status=workflow_run.status,
        search_strategy_summary=workflow_run.search_strategy_summary,
        hard_preferences=workflow_run.hard_preferences or [],
        soft_preferences=workflow_run.soft_preferences or [],
        source_sites=workflow_run.source_sites or [],
        total_site_results=workflow_run.total_site_results,
        total_jobs_found=workflow_run.total_jobs_found,
        total_jobs_returned=workflow_run.total_jobs_returned,
        summary_markdown=workflow_run.summary_markdown,
        jobs=[UnifiedJob.model_validate(job) for job in (workflow_run.jobs or [])],
        site_results=[
            SiteAgentResult.model_validate(site_result)
            for site_result in (workflow_run.site_results or [])
        ],
        notes=workflow_run.notes or [],
        search_model=workflow_run.search_model,
        unification_model=workflow_run.unification_model,
        error_message=workflow_run.error_message,
        current_internal_stage=workflow_run.current_internal_stage,
        current_display_stage=workflow_run.current_display_stage,
        current_display_label=workflow_run.current_display_label,
        current_display_description=workflow_run.current_display_description,
        progress_percent=workflow_run.progress_percent,
        progress_stage_index=workflow_run.progress_stage_index,
        progress_stage_total=workflow_run.progress_stage_total,
        started_at=workflow_run.started_at,
        finished_at=workflow_run.finished_at,
        last_progress_at=workflow_run.last_progress_at,
        created_at=workflow_run.created_at,
        updated_at=workflow_run.updated_at,
    )


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
            parent_request_id=getattr(request.state, "request_id", None),
        )
    except SearchJobWorkflowNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (SearchJobWorkflowEnqueueError, GeminiIntegrationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return _build_workflow_run_response(workflow_run=workflow_run)


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

    return _build_workflow_run_response(workflow_run=workflow_run)
