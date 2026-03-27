from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.search_jobs.models import (
    SearchJobProgressEvent,
    SearchJobSeenJob,
    SearchJobWorkflowRun,
)
from src.workflows.search_job.dedupe import canonical_job_url
from src.workflows.search_job.history import build_job_fingerprint
from src.workflows.search_job.schemas import UnifiedJob

ACTIVE_SEARCH_JOB_WORKFLOW_STATUSES = (
    "queued",
    "planning",
    "searching",
    "deduping",
    "fetching_details",
    "unifying",
)


class SearchJobWorkflowRunsRepository:
    """Database access for search-job workflow runs."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, *, workflow_run_id: UUID) -> SearchJobWorkflowRun | None:
        """Fetch a search-job workflow run by identifier."""
        return await self.session.get(SearchJobWorkflowRun, workflow_run_id)

    async def list_all(self) -> list[SearchJobWorkflowRun]:
        """Return search-job workflow runs ordered by newest first."""
        result = await self.session.execute(
            select(SearchJobWorkflowRun).order_by(desc(SearchJobWorkflowRun.created_at))
        )
        return list(result.scalars().all())

    async def list_for_user(self, *, user_id: str) -> list[SearchJobWorkflowRun]:
        """Return one user's search-job workflow runs ordered by newest first."""
        result = await self.session.execute(
            select(SearchJobWorkflowRun)
            .where(SearchJobWorkflowRun.user_id == user_id)
            .order_by(desc(SearchJobWorkflowRun.created_at))
        )
        return list(result.scalars().all())

    async def get_latest_for_onboarding_session(
        self,
        *,
        onboarding_session_id: UUID,
    ) -> SearchJobWorkflowRun | None:
        """Return the latest search-job run for one onboarding session."""
        result = await self.session.execute(
            select(SearchJobWorkflowRun)
            .where(SearchJobWorkflowRun.onboarding_session_id == onboarding_session_id)
            .order_by(desc(SearchJobWorkflowRun.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_active_for_onboarding_session(
        self,
        *,
        onboarding_session_id: UUID,
        monitoring_mode: bool,
    ) -> SearchJobWorkflowRun | None:
        """Return the newest active run for one onboarding session and mode."""
        result = await self.session.execute(
            select(SearchJobWorkflowRun)
            .where(
                SearchJobWorkflowRun.onboarding_session_id == onboarding_session_id,
                SearchJobWorkflowRun.monitoring_mode == monitoring_mode,
                SearchJobWorkflowRun.status.in_(ACTIVE_SEARCH_JOB_WORKFLOW_STATUSES),
            )
            .order_by(desc(SearchJobWorkflowRun.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_for_user(self, *, user_id: str) -> SearchJobWorkflowRun | None:
        result = await self.session.execute(
            select(SearchJobWorkflowRun)
            .where(SearchJobWorkflowRun.user_id == user_id)
            .order_by(desc(SearchJobWorkflowRun.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    def add(
        self,
        *,
        user_id: str,
        onboarding_session_id: UUID,
        search_strategy_summary: str,
        hard_preferences: list[str],
        soft_preferences: list[str],
        source_sites: list[str],
        monitoring_mode: bool = False,
    ) -> SearchJobWorkflowRun:
        """Create and stage a search-job workflow run."""
        workflow_run = SearchJobWorkflowRun(
            user_id=user_id,
            onboarding_session_id=onboarding_session_id,
            search_strategy_summary=search_strategy_summary,
            hard_preferences=hard_preferences,
            soft_preferences=soft_preferences,
            source_sites=source_sites,
            monitoring_mode=monitoring_mode,
        )
        self.session.add(workflow_run)
        return workflow_run

    def add_progress_event(
        self,
        *,
        workflow_run_id: UUID,
        user_id: str,
        event_type: str,
        display_stage: str,
        display_label: str,
        internal_stage: str | None = None,
        display_description: str | None = None,
        site: str | None = None,
        progress_order: int | None = None,
        display_icon_key: str | None = None,
        display_color_key: str | None = None,
        site_display_name: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> SearchJobProgressEvent:
        event = SearchJobProgressEvent(
            workflow_run_id=workflow_run_id,
            user_id=user_id,
            event_type=event_type,
            internal_stage=internal_stage,
            display_stage=display_stage,
            display_label=display_label,
            display_description=display_description,
            site=site,
            progress_order=progress_order,
            display_icon_key=display_icon_key,
            display_color_key=display_color_key,
            site_display_name=site_display_name,
            payload=payload or {},
        )
        self.session.add(event)
        return event

    async def list_progress_events(self, *, workflow_run_id: UUID) -> list[SearchJobProgressEvent]:
        result = await self.session.execute(
            select(SearchJobProgressEvent)
            .where(SearchJobProgressEvent.workflow_run_id == workflow_run_id)
            .order_by(SearchJobProgressEvent.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_progress_events_after(
        self,
        *,
        workflow_run_id: UUID,
        created_after: datetime | None,
    ) -> list[SearchJobProgressEvent]:
        statement = select(SearchJobProgressEvent).where(
            SearchJobProgressEvent.workflow_run_id == workflow_run_id
        )
        if created_after is not None:
            statement = statement.where(SearchJobProgressEvent.created_at > created_after)
        result = await self.session.execute(
            statement.order_by(SearchJobProgressEvent.created_at.asc())
        )
        return list(result.scalars().all())


class SearchJobSeenJobsRepository:
    """Persistence for per-user delivered-job history used by monitoring runs."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def list_seen_job_urls(self, *, user_id: str) -> list[str]:
        result = await self.session.execute(
            select(SearchJobSeenJob.canonical_job_url).where(SearchJobSeenJob.user_id == user_id)
        )
        return [value for value in result.scalars().all() if value]

    async def list_seen_job_fingerprints(self, *, user_id: str) -> list[str]:
        result = await self.session.execute(
            select(SearchJobSeenJob.job_fingerprint).where(
                SearchJobSeenJob.user_id == user_id,
                SearchJobSeenJob.job_fingerprint.is_not(None),
            )
        )
        return [value for value in result.scalars().all() if value]

    async def record_delivered_jobs(
        self,
        *,
        user_id: str,
        workflow_run_id: UUID,
        jobs: list[UnifiedJob],
        delivered_at: datetime | None = None,
    ) -> None:
        timestamp = delivered_at or datetime.now(UTC)
        if not jobs:
            return

        canonical_urls = [canonical_job_url(job.job_url) for job in jobs if job.job_url]
        if not canonical_urls:
            return

        result = await self.session.execute(
            select(SearchJobSeenJob).where(
                SearchJobSeenJob.user_id == user_id,
                SearchJobSeenJob.canonical_job_url.in_(canonical_urls),
            )
        )
        existing_by_url = {
            item.canonical_job_url: item
            for item in result.scalars().all()
            if item.canonical_job_url
        }

        for job in jobs:
            canonical_url = canonical_job_url(job.job_url)
            fingerprint = build_job_fingerprint(
                title=job.title,
                company_name=job.company_name,
                location=job.location,
            )
            seen_job = existing_by_url.get(canonical_url)
            if seen_job is None:
                seen_job = SearchJobSeenJob(
                    user_id=user_id,
                    workflow_run_id=workflow_run_id,
                    site=job.site,
                    canonical_job_url=canonical_url,
                    job_fingerprint=fingerprint,
                    title=job.title,
                    company_name=job.company_name,
                    location=job.location,
                    source_published_at=job.published_at,
                    first_scraped_at=timestamp,
                    last_scraped_at=timestamp,
                    first_seen_by_user_at=timestamp,
                    last_seen_by_user_at=timestamp,
                    first_delivered_at=timestamp,
                    last_delivered_at=timestamp,
                    times_seen=1,
                    times_delivered=1,
                )
                self.session.add(seen_job)
                existing_by_url[canonical_url] = seen_job
                continue

            seen_job.workflow_run_id = workflow_run_id
            seen_job.site = job.site or seen_job.site
            seen_job.job_fingerprint = fingerprint or seen_job.job_fingerprint
            seen_job.title = job.title or seen_job.title
            seen_job.company_name = job.company_name or seen_job.company_name
            seen_job.location = job.location or seen_job.location
            seen_job.source_published_at = job.published_at or seen_job.source_published_at
            seen_job.last_scraped_at = timestamp
            seen_job.last_seen_by_user_at = timestamp
            seen_job.last_delivered_at = timestamp
            seen_job.times_seen += 1
            seen_job.times_delivered += 1
