from __future__ import annotations

from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_db_session
from src.extensions.arq.client import get_arq_redis
from src.modules.auth.dependencies import AuthContext, require_authenticated_user
from src.modules.auth.security import utcnow
from src.modules.billing.repository import (
    BillingAccessPassesRepository,
    BillingSubscriptionsRepository,
)
from src.modules.job_ai.repository import TrackedJobAiRunsRepository
from src.modules.job_ai.schemas import (
    JobPackArtifactResponse,
    JobPackPayload,
    MatchGapArtifactResponse,
    MatchGapReportPayload,
    TrackedJobAiRunResponse,
)
from src.modules.job_ai.service import (
    JobAiRunNotAllowedError,
    queue_job_pack_run,
    queue_match_gap_run,
)
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
    normalize_job_url,
)
from src.modules.job_tracker.use_cases.save_tracked_job_from_search_run import (
    apply_save_from_search_run_result,
    save_tracked_job_from_search_run,
)

router = APIRouter(prefix="/me/job-tracker", tags=["job-tracker"])
user_auth_dependency = Depends(require_authenticated_user)
db_session_dependency = Depends(get_db_session)
arq_redis_dependency = Depends(get_arq_redis)


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
    result = await save_tracked_job_from_search_run(
        session=session,
        user_id=str(context.user.id),
        payload=payload,
    )
    return apply_save_from_search_run_result(response=response, result=result)


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


@router.post(
    "/jobs/{tracked_job_id}/match-gap/run",
    response_model=TrackedJobAiRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_match_gap_for_tracked_job_route(
    tracked_job_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> TrackedJobAiRunResponse:
    user_id = str(context.user.id)
    await _get_owned_tracked_job_or_404(
        session=session,
        user_id=user_id,
        tracked_job_id=tracked_job_id,
    )
    subscription = await BillingSubscriptionsRepository(session=session).get_by_user_id(
        user_id=user_id
    )
    access_pass = await BillingAccessPassesRepository(session=session).get_active_for_user(
        user_id=user_id
    )
    try:
        run = await queue_match_gap_run(
            session=session,
            arq_redis=arq_redis,
            user_id=user_id,
            tracked_job_id=tracked_job_id,
            subscription=subscription,
            access_pass=access_pass,
            parent_request_id=getattr(context, "request_id", None),
        )
    except JobAiRunNotAllowedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return TrackedJobAiRunResponse.model_validate(run)


@router.get(
    "/jobs/{tracked_job_id}/match-gap",
    response_model=MatchGapArtifactResponse,
)
async def get_match_gap_for_tracked_job_route(
    tracked_job_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> MatchGapArtifactResponse:
    user_id = str(context.user.id)
    await _get_owned_tracked_job_or_404(
        session=session,
        user_id=user_id,
        tracked_job_id=tracked_job_id,
    )
    run = await TrackedJobAiRunsRepository(session=session).get_latest_successful_for_job(
        user_id=user_id,
        tracked_job_id=tracked_job_id,
        run_type="match_gap",
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match report not found.")
    return MatchGapArtifactResponse(
        run=TrackedJobAiRunResponse.model_validate(run),
        report=MatchGapReportPayload.model_validate(run.payload),
    )


@router.post(
    "/jobs/{tracked_job_id}/job-pack/run",
    response_model=TrackedJobAiRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_job_pack_for_tracked_job_route(
    tracked_job_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
    arq_redis: ArqRedis = arq_redis_dependency,
) -> TrackedJobAiRunResponse:
    user_id = str(context.user.id)
    await _get_owned_tracked_job_or_404(
        session=session,
        user_id=user_id,
        tracked_job_id=tracked_job_id,
    )
    subscription = await BillingSubscriptionsRepository(session=session).get_by_user_id(
        user_id=user_id
    )
    access_pass = await BillingAccessPassesRepository(session=session).get_active_for_user(
        user_id=user_id
    )
    try:
        run = await queue_job_pack_run(
            session=session,
            arq_redis=arq_redis,
            user_id=user_id,
            tracked_job_id=tracked_job_id,
            subscription=subscription,
            access_pass=access_pass,
            parent_request_id=getattr(context, "request_id", None),
        )
    except JobAiRunNotAllowedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return TrackedJobAiRunResponse.model_validate(run)


@router.get(
    "/jobs/{tracked_job_id}/job-pack",
    response_model=JobPackArtifactResponse,
)
async def get_job_pack_for_tracked_job_route(
    tracked_job_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> JobPackArtifactResponse:
    user_id = str(context.user.id)
    await _get_owned_tracked_job_or_404(
        session=session,
        user_id=user_id,
        tracked_job_id=tracked_job_id,
    )
    run = await TrackedJobAiRunsRepository(session=session).get_latest_successful_for_job(
        user_id=user_id,
        tracked_job_id=tracked_job_id,
        run_type="job_pack",
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tailor Pack not found.")
    return JobPackArtifactResponse(
        run=TrackedJobAiRunResponse.model_validate(run),
        job_pack=JobPackPayload.model_validate(run.payload),
    )


@router.get("/ai-runs/{run_id}", response_model=TrackedJobAiRunResponse)
async def get_tracked_job_ai_run_route(
    run_id: UUID,
    context: AuthContext = user_auth_dependency,
    session: AsyncSession = db_session_dependency,
) -> TrackedJobAiRunResponse:
    run = await TrackedJobAiRunsRepository(session=session).get_by_id(run_id=run_id)
    if run is None or run.user_id != str(context.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI run not found.")
    return TrackedJobAiRunResponse.model_validate(run)


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
