from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.search_jobs.models import SearchJobProgressEvent, SearchJobWorkflowRun


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
    ) -> SearchJobWorkflowRun:
        """Create and stage a search-job workflow run."""
        workflow_run = SearchJobWorkflowRun(
            user_id=user_id,
            onboarding_session_id=onboarding_session_id,
            search_strategy_summary=search_strategy_summary,
            hard_preferences=hard_preferences,
            soft_preferences=soft_preferences,
            source_sites=source_sites,
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
