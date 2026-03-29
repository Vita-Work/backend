from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.billing.repository import (
    BillingAccessPassesRepository,
    BillingSubscriptionsRepository,
)
from src.modules.billing.service import build_billing_entitlements, limit_visible_search_jobs
from src.modules.job_tracker.repository import TrackedJobsRepository
from src.modules.job_tracker.schemas import (
    SaveTrackedJobFromSearchRunRequest,
    SaveTrackedJobFromSearchRunResponse,
)
from src.modules.job_tracker.service import (
    build_tracked_job_response,
    create_status_change_activity_payload,
    create_tracked_job_from_unified_job,
    normalize_job_url,
)
from src.modules.search_jobs.use_cases.get_search_job_run import get_search_job_workflow_run
from src.workflows.search_job.schemas import UnifiedJob


@dataclass(slots=True)
class SaveTrackedJobFromSearchRunResult:
    payload: SaveTrackedJobFromSearchRunResponse
    status_code: int


async def save_tracked_job_from_search_run(
    *,
    session: AsyncSession,
    user_id: str,
    payload: SaveTrackedJobFromSearchRunRequest,
) -> SaveTrackedJobFromSearchRunResult:
    workflow_run = await get_search_job_workflow_run(
        session=session,
        workflow_run_id=payload.workflow_run_id,
    )
    if workflow_run is None or workflow_run.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    if not workflow_run.jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No jobs found in workflow run.",
        )

    subscription = await BillingSubscriptionsRepository(session=session).get_by_user_id(
        user_id=user_id
    )
    access_pass = await BillingAccessPassesRepository(session=session).get_active_for_user(
        user_id=user_id
    )
    entitlements = build_billing_entitlements(subscription=subscription, access_pass=access_pass)
    visible_jobs = limit_visible_search_jobs(
        jobs=workflow_run.jobs or [],
        entitlements=entitlements,
    )

    selected_job = _select_visible_job(visible_jobs=visible_jobs, payload=payload)

    repository = TrackedJobsRepository(session=session)
    normalized_job_url = normalize_job_url(selected_job.job_url)
    existing = None
    if normalized_job_url is not None:
        existing = await repository.get_job_by_user_and_source_url(
            user_id=user_id,
            source_job_url=normalized_job_url,
        )
    if existing is not None:
        return SaveTrackedJobFromSearchRunResult(
            payload=SaveTrackedJobFromSearchRunResponse(
                tracked_job=build_tracked_job_response(tracked_job=existing),
                already_saved=True,
                tracked_job_id=existing.id,
                tracker_status=existing.status,
            ),
            status_code=status.HTTP_200_OK,
        )

    tracked_job = repository.add_job(
        **create_tracked_job_from_unified_job(
            user_id=user_id,
            workflow_run_id=payload.workflow_run_id,
            job=selected_job,
        )
    )
    await session.flush()
    repository.add_activity(
        **create_status_change_activity_payload(
            user_id=user_id,
            tracked_job_id=tracked_job.id,
            from_status=None,
            to_status=tracked_job.status,
        )
    )
    await session.commit()
    await session.refresh(tracked_job)

    return SaveTrackedJobFromSearchRunResult(
        payload=SaveTrackedJobFromSearchRunResponse(
            tracked_job=build_tracked_job_response(tracked_job=tracked_job),
            already_saved=False,
            tracked_job_id=tracked_job.id,
            tracker_status=tracked_job.status,
        ),
        status_code=status.HTTP_201_CREATED,
    )


def apply_save_from_search_run_result(
    *,
    response: Response,
    result: SaveTrackedJobFromSearchRunResult,
) -> SaveTrackedJobFromSearchRunResponse:
    response.status_code = result.status_code
    return result.payload


def _select_visible_job(
    *,
    visible_jobs: list[dict],
    payload: SaveTrackedJobFromSearchRunRequest,
) -> UnifiedJob:
    if payload.job_index is not None:
        if payload.job_index < 0 or payload.job_index >= len(visible_jobs):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return UnifiedJob.model_validate(visible_jobs[payload.job_index])

    normalized_target_url = normalize_job_url(payload.job_url)
    for item in visible_jobs:
        job = UnifiedJob.model_validate(item)
        if normalize_job_url(job.job_url) == normalized_target_url:
            return job

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
