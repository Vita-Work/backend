from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.search_jobs.models import SearchJobWorkflowRun
from src.modules.search_jobs.repository import SearchJobWorkflowRunsRepository


async def get_search_job_workflow_run(
    *,
    session: AsyncSession,
    workflow_run_id: UUID,
) -> SearchJobWorkflowRun | None:
    """Fetch a persisted search-job workflow run."""
    repository = SearchJobWorkflowRunsRepository(session=session)
    return await repository.get_by_id(workflow_run_id=workflow_run_id)
