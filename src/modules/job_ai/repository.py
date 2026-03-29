from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.job_ai.models import TrackedJobAiRun


class TrackedJobAiRunsRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, *, run_id: UUID) -> TrackedJobAiRun | None:
        return await self.session.get(TrackedJobAiRun, run_id)

    def add_run(self, **kwargs) -> TrackedJobAiRun:
        run = TrackedJobAiRun(**kwargs)
        self.session.add(run)
        return run

    async def get_latest_for_job(
        self,
        *,
        user_id: str,
        tracked_job_id: UUID,
        run_type: str,
    ) -> TrackedJobAiRun | None:
        result = await self.session.execute(
            select(TrackedJobAiRun)
            .where(
                TrackedJobAiRun.user_id == user_id,
                TrackedJobAiRun.tracked_job_id == tracked_job_id,
                TrackedJobAiRun.run_type == run_type,
            )
            .order_by(desc(TrackedJobAiRun.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_successful_for_job(
        self,
        *,
        user_id: str,
        tracked_job_id: UUID,
        run_type: str,
    ) -> TrackedJobAiRun | None:
        result = await self.session.execute(
            select(TrackedJobAiRun)
            .where(
                TrackedJobAiRun.user_id == user_id,
                TrackedJobAiRun.tracked_job_id == tracked_job_id,
                TrackedJobAiRun.run_type == run_type,
                TrackedJobAiRun.status == "completed",
            )
            .order_by(desc(TrackedJobAiRun.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_successful_for_job_with_hashes(
        self,
        *,
        user_id: str,
        tracked_job_id: UUID,
        run_type: str,
        source_profile_hash: str,
        source_job_hash: str,
    ) -> TrackedJobAiRun | None:
        result = await self.session.execute(
            select(TrackedJobAiRun)
            .where(
                TrackedJobAiRun.user_id == user_id,
                TrackedJobAiRun.tracked_job_id == tracked_job_id,
                TrackedJobAiRun.run_type == run_type,
                TrackedJobAiRun.status == "completed",
                TrackedJobAiRun.source_profile_hash == source_profile_hash,
                TrackedJobAiRun.source_job_hash == source_job_hash,
            )
            .order_by(desc(TrackedJobAiRun.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_successful_runs_for_user(
        self,
        *,
        user_id: str,
        run_type: str,
    ) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(TrackedJobAiRun)
            .where(
                TrackedJobAiRun.user_id == user_id,
                TrackedJobAiRun.run_type == run_type,
                TrackedJobAiRun.status == "completed",
            )
        )
        return int(result.scalar_one() or 0)
