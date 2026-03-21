from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.extraction.models import ExtractionWorkflowRun


class ExtractionWorkflowRunsRepository:
    """Database access for extraction workflow runs."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, *, workflow_run_id: UUID) -> ExtractionWorkflowRun | None:
        """Fetch a workflow run by identifier."""
        return await self.session.get(ExtractionWorkflowRun, workflow_run_id)

    def add(
        self,
        *,
        user_id: str,
        onboarding_session_id: UUID | None,
        status: str,
        storage_bucket: str,
        storage_key: str,
        storage_uri: str,
        cv_filename: str,
        cv_content_type: str,
        cv_extension: str,
        cv_size_bytes: int,
        cv_sha256: str,
        extraction_strategy: str,
        inline_text_characters: int | None,
    ) -> ExtractionWorkflowRun:
        """Create and stage a workflow run in the current session."""
        workflow_run = ExtractionWorkflowRun(
            user_id=user_id,
            onboarding_session_id=onboarding_session_id,
            status=status,
            storage_bucket=storage_bucket,
            storage_key=storage_key,
            storage_uri=storage_uri,
            cv_filename=cv_filename,
            cv_content_type=cv_content_type,
            cv_extension=cv_extension,
            cv_size_bytes=cv_size_bytes,
            cv_sha256=cv_sha256,
            extraction_strategy=extraction_strategy,
            inline_text_characters=inline_text_characters,
        )
        self.session.add(workflow_run)
        return workflow_run
