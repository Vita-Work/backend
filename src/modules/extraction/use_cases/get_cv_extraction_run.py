from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.extraction.models import ExtractionWorkflowRun
from src.modules.extraction.repository import ExtractionWorkflowRunsRepository


async def get_cv_extraction_workflow_run(
    *,
    session: AsyncSession,
    workflow_run_id: UUID,
) -> ExtractionWorkflowRun | None:
    """Fetch a persisted extraction workflow run."""
    repository = ExtractionWorkflowRunsRepository(session=session)
    return await repository.get_by_id(workflow_run_id=workflow_run_id)
