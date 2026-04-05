from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.extraction.models import ExtractionProgressEvent, ExtractionWorkflowRun


class ExtractionWorkflowRunsRepository:
    """Database access for extraction workflow runs."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, *, workflow_run_id: UUID) -> ExtractionWorkflowRun | None:
        """Fetch a workflow run by identifier."""
        return await self.session.get(ExtractionWorkflowRun, workflow_run_id)

    async def list_all(self) -> list[ExtractionWorkflowRun]:
        """Return workflow runs ordered by newest first."""
        result = await self.session.execute(
            select(ExtractionWorkflowRun).order_by(desc(ExtractionWorkflowRun.created_at))
        )
        return list(result.scalars().all())

    async def get_latest_for_user(self, *, user_id: str) -> ExtractionWorkflowRun | None:
        result = await self.session.execute(
            select(ExtractionWorkflowRun)
            .where(ExtractionWorkflowRun.user_id == user_id)
            .order_by(desc(ExtractionWorkflowRun.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

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

    def add_progress_event(
        self,
        *,
        workflow_run_id: UUID,
        user_id: str,
        event_type: str,
        ui_phase: str,
        ui_label: str,
        ui_description: str | None,
        progress_percent: int | None,
        progress_stage_index: int | None,
        progress_stage_total: int | None,
        payload: dict[str, object] | None = None,
    ) -> ExtractionProgressEvent:
        event = ExtractionProgressEvent(
            workflow_run_id=workflow_run_id,
            user_id=user_id,
            event_type=event_type,
            ui_phase=ui_phase,
            ui_label=ui_label,
            ui_description=ui_description,
            progress_percent=progress_percent,
            progress_stage_index=progress_stage_index,
            progress_stage_total=progress_stage_total,
            payload=payload or {},
        )
        self.session.add(event)
        return event

    async def list_progress_events(self, *, workflow_run_id: UUID) -> list[ExtractionProgressEvent]:
        result = await self.session.execute(
            select(ExtractionProgressEvent)
            .where(ExtractionProgressEvent.workflow_run_id == workflow_run_id)
            .order_by(ExtractionProgressEvent.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_latest_failure_event(
        self,
        *,
        workflow_run_id: UUID,
    ) -> ExtractionProgressEvent | None:
        result = await self.session.execute(
            select(ExtractionProgressEvent)
            .where(
                ExtractionProgressEvent.workflow_run_id == workflow_run_id,
                ExtractionProgressEvent.ui_phase == "failed",
            )
            .order_by(desc(ExtractionProgressEvent.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_progress_events_after(
        self,
        *,
        workflow_run_id: UUID,
        created_after: datetime | None,
    ) -> list[ExtractionProgressEvent]:
        statement = select(ExtractionProgressEvent).where(
            ExtractionProgressEvent.workflow_run_id == workflow_run_id
        )
        if created_after is not None:
            statement = statement.where(ExtractionProgressEvent.created_at > created_after)
        result = await self.session.execute(
            statement.order_by(ExtractionProgressEvent.created_at.asc())
        )
        return list(result.scalars().all())
