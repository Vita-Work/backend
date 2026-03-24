from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.search_jobs.models import SearchJobWorkflowRun


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
