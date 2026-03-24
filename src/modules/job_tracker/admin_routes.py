from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db_session
from src.modules.auth.dependencies import AuthContext, require_admin
from src.modules.job_tracker.repository import TrackedJobsRepository
from src.modules.job_tracker.schemas import (
    AdminUpdateTrackedJobRequest,
    JobTrackerListQuery,
    JobTrackerMetricsResponse,
    TrackedJobDetailResponse,
    TrackedJobResponse,
)
from src.modules.job_tracker.service import (
    apply_job_updates,
    apply_status_transition,
    build_tracked_job_detail,
    compute_job_tracker_metrics,
)

router = APIRouter(prefix="/admin/job-tracker", tags=["admin", "job-tracker-admin"])
admin_dependency = Depends(require_admin)
db_session_dependency = Depends(get_db_session)


@router.get("/jobs", response_model=list[TrackedJobResponse])
async def list_job_tracker_jobs_admin_route(
    status_value: str | None = Query(default=None, alias="status"),
    site: str | None = None,
    priority: str | None = None,
    has_follow_up: bool | None = None,
    archived: bool = False,
    search: str | None = None,
    sort: str = "updated_at",
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[TrackedJobResponse]:
    query = JobTrackerListQuery(
        status=status_value,
        site=site,
        priority=priority,
        has_follow_up=has_follow_up,
        archived=archived,
        search=search,
        sort=sort,
    )
    jobs = await TrackedJobsRepository(session=session).list_jobs(query=query)
    return [TrackedJobResponse.model_validate(job) for job in jobs]


@router.get("/users/{user_id}/jobs", response_model=list[TrackedJobResponse])
async def list_user_job_tracker_jobs_admin_route(
    user_id: UUID,
    status_value: str | None = Query(default=None, alias="status"),
    site: str | None = None,
    priority: str | None = None,
    has_follow_up: bool | None = None,
    archived: bool = False,
    search: str | None = None,
    sort: str = "updated_at",
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[TrackedJobResponse]:
    query = JobTrackerListQuery(
        status=status_value,
        site=site,
        priority=priority,
        has_follow_up=has_follow_up,
        archived=archived,
        search=search,
        sort=sort,
    )
    jobs = await TrackedJobsRepository(session=session).list_jobs_for_user(
        user_id=str(user_id), query=query
    )
    return [TrackedJobResponse.model_validate(job) for job in jobs]


@router.get("/users/{user_id}/metrics", response_model=JobTrackerMetricsResponse)
async def get_user_job_tracker_metrics_admin_route(
    user_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> JobTrackerMetricsResponse:
    repository = TrackedJobsRepository(session=session)
    jobs = await repository.list_jobs_for_user(user_id=str(user_id), query=JobTrackerListQuery())
    activities = await repository.list_activities_for_user(user_id=str(user_id))
    return compute_job_tracker_metrics(jobs=jobs, activities=activities)


@router.get("/jobs/{tracked_job_id}", response_model=TrackedJobDetailResponse)
async def get_job_tracker_job_admin_route(
    tracked_job_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobDetailResponse:
    repository = TrackedJobsRepository(session=session)
    tracked_job = await repository.get_job_by_id(tracked_job_id=tracked_job_id)
    if tracked_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked job not found.")
    activities = await repository.list_job_activities(tracked_job_id=tracked_job_id)
    contacts = await repository.list_job_contacts(tracked_job_id=tracked_job_id)
    return build_tracked_job_detail(
        tracked_job=tracked_job,
        activities=activities,
        contacts=contacts,
    )


@router.patch("/jobs/{tracked_job_id}", response_model=TrackedJobResponse)
async def update_job_tracker_job_admin_route(
    tracked_job_id: UUID,
    payload: AdminUpdateTrackedJobRequest,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobResponse:
    repository = TrackedJobsRepository(session=session)
    tracked_job = await repository.get_job_by_id(tracked_job_id=tracked_job_id)
    if tracked_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked job not found.")
    apply_job_updates(tracked_job=tracked_job, payload=payload)
    if payload.status is not None:
        apply_status_transition(tracked_job=tracked_job, status=payload.status)
    if payload.archived_at is not None:
        tracked_job.archived_at = payload.archived_at
    await session.commit()
    await session.refresh(tracked_job)
    return TrackedJobResponse.model_validate(tracked_job)


@router.delete("/jobs/{tracked_job_id}", response_model=TrackedJobResponse)
async def delete_job_tracker_job_admin_route(
    tracked_job_id: UUID,
    _: AuthContext = admin_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobResponse:
    repository = TrackedJobsRepository(session=session)
    tracked_job = await repository.get_job_by_id(tracked_job_id=tracked_job_id)
    if tracked_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked job not found.")
    apply_status_transition(tracked_job=tracked_job, status="archived")
    await session.commit()
    await session.refresh(tracked_job)
    return TrackedJobResponse.model_validate(tracked_job)
