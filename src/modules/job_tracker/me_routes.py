from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db_session
from src.modules.auth.dependencies import AuthContext, require_authenticated_user
from src.modules.auth.security import utcnow
from src.modules.job_tracker.constants import (
    TRACKED_JOB_ACTIVITY_FOLLOW_UP,
    TRACKED_JOB_STATUS_ARCHIVED,
)
from src.modules.job_tracker.repository import TrackedJobsRepository
from src.modules.job_tracker.schemas import (
    BulkArchiveTrackedJobsRequest,
    BulkUpdateTrackedJobsStatusRequest,
    CreateTrackedJobActivityRequest,
    CreateTrackedJobContactRequest,
    CreateTrackedJobRequest,
    JobTrackerActivityFeedItemResponse,
    JobTrackerDashboardResponse,
    JobTrackerListQuery,
    JobTrackerMetricsResponse,
    SaveTrackedJobFromSearchRunRequest,
    SaveTrackedJobFromSearchRunResponse,
    TrackedJobActivityResponse,
    TrackedJobContactResponse,
    TrackedJobDetailResponse,
    TrackedJobResponse,
    UpdateTrackedJobRequest,
    UpdateTrackedJobStatusRequest,
)
from src.modules.job_tracker.service import (
    apply_job_updates,
    apply_status_transition,
    build_activity_feed,
    build_job_tracker_dashboard,
    build_tracked_job_detail,
    build_tracked_job_response,
    build_tracked_jobs_csv,
    compute_job_tracker_metrics,
    create_activity_payload,
    create_contact_payload,
    create_status_change_activity_payload,
    create_tracked_job_from_manual_payload,
    create_tracked_job_from_unified_job,
    normalize_job_url,
)
from src.modules.search_jobs.use_cases.get_search_job_run import get_search_job_workflow_run
from src.workflows.search_job.schemas import UnifiedJob

router = APIRouter(prefix="/me/job-tracker", tags=["job-tracker"])
user_auth_dependency = Depends(require_authenticated_user)
db_session_dependency = Depends(get_db_session)


async def _get_owned_tracked_job_or_404(
    *,
    session: AsyncSession,
    user_id: str,
    tracked_job_id: UUID,
):
    repository = TrackedJobsRepository(session=session)
    tracked_job = await repository.get_job_by_id(tracked_job_id=tracked_job_id)
    if tracked_job is None or tracked_job.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked job not found.")
    return tracked_job


def _build_query(
    *,
    status_value: str | None,
    site: str | None,
    priority: str | None,
    has_follow_up: bool | None,
    archived: bool,
    search: str | None,
    sort: str,
) -> JobTrackerListQuery:
    return JobTrackerListQuery(
        status=status_value,
        site=site,
        priority=priority,
        has_follow_up=has_follow_up,
        archived=archived,
        search=search,
        sort=sort,
    )


@router.get("/jobs", response_model=list[TrackedJobResponse])
async def list_my_tracked_jobs_route(
    status_value: str | None = Query(default=None, alias="status"),
    site: str | None = None,
    priority: str | None = None,
    has_follow_up: bool | None = None,
    archived: bool = False,
    search: str | None = None,
    sort: str = "updated_at",
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[TrackedJobResponse]:
    query = _build_query(
        status_value=status_value,
        site=site,
        priority=priority,
        has_follow_up=has_follow_up,
        archived=archived,
        search=search,
        sort=sort,
    )
    jobs = await TrackedJobsRepository(session=session).list_jobs_for_user(
        user_id=str(context.user.id),
        query=query,
    )
    return [build_tracked_job_response(tracked_job=job) for job in jobs]


@router.post("/jobs", response_model=TrackedJobResponse, status_code=status.HTTP_201_CREATED)
async def create_my_tracked_job_route(
    payload: CreateTrackedJobRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobResponse:
    repository = TrackedJobsRepository(session=session)
    normalized_url = normalize_job_url(payload.source_job_url)
    if normalized_url is not None:
        existing = await repository.get_job_by_user_and_source_url(
            user_id=str(context.user.id),
            source_job_url=normalized_url,
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tracked job with this URL already exists.",
            )

    tracked_job = repository.add_job(
        **create_tracked_job_from_manual_payload(
            user_id=str(context.user.id),
            payload=payload,
        )
    )
    await session.flush()
    repository.add_activity(
        **create_status_change_activity_payload(
            user_id=str(context.user.id),
            tracked_job_id=tracked_job.id,
            from_status=None,
            to_status=tracked_job.status,
        )
    )
    await session.commit()
    await session.refresh(tracked_job)
    return build_tracked_job_response(tracked_job=tracked_job)


@router.post(
    "/jobs/from-search-run",
    response_model=SaveTrackedJobFromSearchRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_my_tracked_job_from_search_run_route(
    payload: SaveTrackedJobFromSearchRunRequest,
    response: Response,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> SaveTrackedJobFromSearchRunResponse:
    workflow_run = await get_search_job_workflow_run(
        session=session,
        workflow_run_id=payload.workflow_run_id,
    )
    if workflow_run is None or workflow_run.user_id != str(context.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found.")
    if not workflow_run.jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No jobs found in workflow run.",
        )

    selected_job: UnifiedJob | None = None
    if payload.job_index is not None:
        if payload.job_index < 0 or payload.job_index >= len(workflow_run.jobs):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        selected_job = UnifiedJob.model_validate(workflow_run.jobs[payload.job_index])
    else:
        normalized_target_url = normalize_job_url(payload.job_url)
        for item in workflow_run.jobs:
            job = UnifiedJob.model_validate(item)
            if normalize_job_url(job.job_url) == normalized_target_url:
                selected_job = job
                break
    if selected_job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    repository = TrackedJobsRepository(session=session)
    normalized_job_url = normalize_job_url(selected_job.job_url)
    existing = None
    if normalized_job_url is not None:
        existing = await repository.get_job_by_user_and_source_url(
            user_id=str(context.user.id),
            source_job_url=normalized_job_url,
        )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        tracked_job_response = build_tracked_job_response(tracked_job=existing)
        return SaveTrackedJobFromSearchRunResponse(
            tracked_job=tracked_job_response,
            already_saved=True,
            tracked_job_id=existing.id,
            tracker_status=existing.status,
        )

    tracked_job = repository.add_job(
        **create_tracked_job_from_unified_job(
            user_id=str(context.user.id),
            workflow_run_id=payload.workflow_run_id,
            job=selected_job,
        )
    )
    await session.flush()
    repository.add_activity(
        **create_status_change_activity_payload(
            user_id=str(context.user.id),
            tracked_job_id=tracked_job.id,
            from_status=None,
            to_status=tracked_job.status,
        )
    )
    await session.commit()
    await session.refresh(tracked_job)
    tracked_job_response = build_tracked_job_response(tracked_job=tracked_job)
    return SaveTrackedJobFromSearchRunResponse(
        tracked_job=tracked_job_response,
        already_saved=False,
        tracked_job_id=tracked_job.id,
        tracker_status=tracked_job.status,
    )


@router.get("/jobs/{tracked_job_id}", response_model=TrackedJobDetailResponse)
async def get_my_tracked_job_route(
    tracked_job_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobDetailResponse:
    repository = TrackedJobsRepository(session=session)
    tracked_job = await _get_owned_tracked_job_or_404(
        session=session,
        user_id=str(context.user.id),
        tracked_job_id=tracked_job_id,
    )
    activities = await repository.list_job_activities(tracked_job_id=tracked_job_id)
    contacts = await repository.list_job_contacts(tracked_job_id=tracked_job_id)
    return build_tracked_job_detail(
        tracked_job=tracked_job,
        activities=activities,
        contacts=contacts,
    )


@router.patch("/jobs/{tracked_job_id}", response_model=TrackedJobResponse)
async def update_my_tracked_job_route(
    tracked_job_id: UUID,
    payload: UpdateTrackedJobRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobResponse:
    tracked_job = await _get_owned_tracked_job_or_404(
        session=session,
        user_id=str(context.user.id),
        tracked_job_id=tracked_job_id,
    )
    apply_job_updates(tracked_job=tracked_job, payload=payload)
    await session.commit()
    await session.refresh(tracked_job)
    return build_tracked_job_response(tracked_job=tracked_job)


@router.delete("/jobs/{tracked_job_id}", response_model=TrackedJobResponse)
async def archive_my_tracked_job_route(
    tracked_job_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobResponse:
    repository = TrackedJobsRepository(session=session)
    tracked_job = await _get_owned_tracked_job_or_404(
        session=session,
        user_id=str(context.user.id),
        tracked_job_id=tracked_job_id,
    )
    previous_status = tracked_job.status
    apply_status_transition(tracked_job=tracked_job, status=TRACKED_JOB_STATUS_ARCHIVED)
    repository.add_activity(
        **create_status_change_activity_payload(
            user_id=str(context.user.id),
            tracked_job_id=tracked_job.id,
            from_status=previous_status,
            to_status=tracked_job.status,
        )
    )
    await session.commit()
    await session.refresh(tracked_job)
    return build_tracked_job_response(tracked_job=tracked_job)


@router.post("/jobs/{tracked_job_id}/status", response_model=TrackedJobResponse)
async def update_my_tracked_job_status_route(
    tracked_job_id: UUID,
    payload: UpdateTrackedJobStatusRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobResponse:
    repository = TrackedJobsRepository(session=session)
    tracked_job = await _get_owned_tracked_job_or_404(
        session=session,
        user_id=str(context.user.id),
        tracked_job_id=tracked_job_id,
    )
    previous_status = tracked_job.status
    apply_status_transition(tracked_job=tracked_job, status=payload.status)
    repository.add_activity(
        **create_status_change_activity_payload(
            user_id=str(context.user.id),
            tracked_job_id=tracked_job.id,
            from_status=previous_status,
            to_status=payload.status,
        )
    )
    await session.commit()
    await session.refresh(tracked_job)
    return build_tracked_job_response(tracked_job=tracked_job)


@router.get(
    "/jobs/{tracked_job_id}/activities",
    response_model=list[TrackedJobActivityResponse],
)
async def list_my_tracked_job_activities_route(
    tracked_job_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[TrackedJobActivityResponse]:
    repository = TrackedJobsRepository(session=session)
    await _get_owned_tracked_job_or_404(
        session=session,
        user_id=str(context.user.id),
        tracked_job_id=tracked_job_id,
    )
    activities = await repository.list_job_activities(tracked_job_id=tracked_job_id)
    return [TrackedJobActivityResponse.model_validate(item) for item in activities]


@router.post(
    "/jobs/{tracked_job_id}/activities",
    response_model=TrackedJobActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_tracked_job_activity_route(
    tracked_job_id: UUID,
    payload: CreateTrackedJobActivityRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobActivityResponse:
    repository = TrackedJobsRepository(session=session)
    await _get_owned_tracked_job_or_404(
        session=session,
        user_id=str(context.user.id),
        tracked_job_id=tracked_job_id,
    )
    activity = repository.add_activity(
        **create_activity_payload(
            user_id=str(context.user.id),
            tracked_job_id=tracked_job_id,
            payload=payload,
        )
    )
    await session.flush()
    if payload.activity_type == TRACKED_JOB_ACTIVITY_FOLLOW_UP:
        await repository.recalculate_next_follow_up_at(tracked_job_id=tracked_job_id)
    await session.commit()
    await session.refresh(activity)
    return TrackedJobActivityResponse.model_validate(activity)


@router.post(
    "/jobs/{tracked_job_id}/activities/{activity_id}/complete",
    response_model=TrackedJobActivityResponse,
)
async def complete_my_follow_up_route(
    tracked_job_id: UUID,
    activity_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobActivityResponse:
    repository = TrackedJobsRepository(session=session)
    await _get_owned_tracked_job_or_404(
        session=session,
        user_id=str(context.user.id),
        tracked_job_id=tracked_job_id,
    )
    activity = await repository.get_activity_by_id(
        tracked_job_id=tracked_job_id,
        activity_id=activity_id,
    )
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")
    if activity.activity_type != TRACKED_JOB_ACTIVITY_FOLLOW_UP:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only follow-up activities can be completed.",
        )
    activity.completed_at = utcnow()
    await repository.recalculate_next_follow_up_at(tracked_job_id=tracked_job_id)
    await session.commit()
    await session.refresh(activity)
    return TrackedJobActivityResponse.model_validate(activity)


@router.get(
    "/jobs/{tracked_job_id}/contacts",
    response_model=list[TrackedJobContactResponse],
)
async def list_my_tracked_job_contacts_route(
    tracked_job_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[TrackedJobContactResponse]:
    repository = TrackedJobsRepository(session=session)
    await _get_owned_tracked_job_or_404(
        session=session,
        user_id=str(context.user.id),
        tracked_job_id=tracked_job_id,
    )
    contacts = await repository.list_job_contacts(tracked_job_id=tracked_job_id)
    return [TrackedJobContactResponse.model_validate(item) for item in contacts]


@router.post(
    "/jobs/{tracked_job_id}/contacts",
    response_model=TrackedJobContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_my_tracked_job_contact_route(
    tracked_job_id: UUID,
    payload: CreateTrackedJobContactRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobContactResponse:
    repository = TrackedJobsRepository(session=session)
    await _get_owned_tracked_job_or_404(
        session=session,
        user_id=str(context.user.id),
        tracked_job_id=tracked_job_id,
    )
    contact = repository.add_contact(
        **create_contact_payload(
            user_id=str(context.user.id),
            tracked_job_id=tracked_job_id,
            payload=payload,
        )
    )
    await session.commit()
    await session.refresh(contact)
    return TrackedJobContactResponse.model_validate(contact)


@router.get("/metrics", response_model=JobTrackerMetricsResponse)
async def get_my_job_tracker_metrics_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> JobTrackerMetricsResponse:
    repository = TrackedJobsRepository(session=session)
    jobs = await repository.list_jobs_for_user(
        user_id=str(context.user.id),
        query=JobTrackerListQuery(archived=False),
    )
    activities = await repository.list_activities_for_user(user_id=str(context.user.id))
    return compute_job_tracker_metrics(jobs=jobs, activities=activities)


@router.get("/dashboard", response_model=JobTrackerDashboardResponse)
async def get_my_job_tracker_dashboard_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> JobTrackerDashboardResponse:
    repository = TrackedJobsRepository(session=session)
    jobs = await repository.list_jobs_for_user(
        user_id=str(context.user.id),
        query=JobTrackerListQuery(archived=False),
    )
    activities = await repository.list_activities_for_user(user_id=str(context.user.id))
    return build_job_tracker_dashboard(jobs=jobs, activities=activities)


@router.get("/activity-feed", response_model=list[JobTrackerActivityFeedItemResponse])
async def get_my_job_tracker_activity_feed_route(
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[JobTrackerActivityFeedItemResponse]:
    repository = TrackedJobsRepository(session=session)
    jobs = await repository.list_jobs_for_user(
        user_id=str(context.user.id),
        query=JobTrackerListQuery(archived=False),
    )
    activities = await repository.list_activities_for_user(user_id=str(context.user.id))
    return build_activity_feed(jobs=jobs, activities=activities)[:25]


@router.post("/jobs/bulk/status", response_model=list[TrackedJobResponse])
async def bulk_update_my_tracked_jobs_status_route(
    payload: BulkUpdateTrackedJobsStatusRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[TrackedJobResponse]:
    repository = TrackedJobsRepository(session=session)
    updated_jobs = []
    for tracked_job_id in payload.tracked_job_ids:
        tracked_job = await _get_owned_tracked_job_or_404(
            session=session,
            user_id=str(context.user.id),
            tracked_job_id=tracked_job_id,
        )
        previous_status = tracked_job.status
        apply_status_transition(tracked_job=tracked_job, status=payload.status)
        repository.add_activity(
            **create_status_change_activity_payload(
                user_id=str(context.user.id),
                tracked_job_id=tracked_job.id,
                from_status=previous_status,
                to_status=payload.status,
            )
        )
        updated_jobs.append(tracked_job)
    await session.commit()
    for tracked_job in updated_jobs:
        await session.refresh(tracked_job)
    return [build_tracked_job_response(tracked_job=item) for item in updated_jobs]


@router.post("/jobs/bulk/archive", response_model=list[TrackedJobResponse])
async def bulk_archive_my_tracked_jobs_route(
    payload: BulkArchiveTrackedJobsRequest,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> list[TrackedJobResponse]:
    repository = TrackedJobsRepository(session=session)
    archived_jobs = []
    for tracked_job_id in payload.tracked_job_ids:
        tracked_job = await _get_owned_tracked_job_or_404(
            session=session,
            user_id=str(context.user.id),
            tracked_job_id=tracked_job_id,
        )
        previous_status = tracked_job.status
        apply_status_transition(tracked_job=tracked_job, status=TRACKED_JOB_STATUS_ARCHIVED)
        repository.add_activity(
            **create_status_change_activity_payload(
                user_id=str(context.user.id),
                tracked_job_id=tracked_job.id,
                from_status=previous_status,
                to_status=tracked_job.status,
            )
        )
        archived_jobs.append(tracked_job)
    await session.commit()
    for tracked_job in archived_jobs:
        await session.refresh(tracked_job)
    return [build_tracked_job_response(tracked_job=item) for item in archived_jobs]


@router.get("/export.csv")
async def export_my_job_tracker_csv_route(
    status_value: str | None = Query(default=None, alias="status"),
    site: str | None = None,
    priority: str | None = None,
    has_follow_up: bool | None = None,
    archived: bool = False,
    search: str | None = None,
    sort: str = "updated_at",
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
):
    query = _build_query(
        status_value=status_value,
        site=site,
        priority=priority,
        has_follow_up=has_follow_up,
        archived=archived,
        search=search,
        sort=sort,
    )
    jobs = await TrackedJobsRepository(session=session).list_jobs_for_user(
        user_id=str(context.user.id),
        query=query,
    )
    csv_payload = build_tracked_jobs_csv(jobs=jobs)
    return StreamingResponse(
        iter([csv_payload]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="job-tracker.csv"'},
    )
