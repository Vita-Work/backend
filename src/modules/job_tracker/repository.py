from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.job_tracker.constants import (
    TRACKED_JOB_ACTIVITY_FOLLOW_UP,
    TRACKED_JOB_SORT_APPLIED_AT,
    TRACKED_JOB_SORT_DEADLINE_AT,
    TRACKED_JOB_SORT_NEXT_FOLLOW_UP_AT,
)
from src.modules.job_tracker.models import TrackedJob, TrackedJobActivity, TrackedJobContact
from src.modules.job_tracker.schemas import JobTrackerListQuery


class TrackedJobsRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_job_by_id(self, *, tracked_job_id: UUID) -> TrackedJob | None:
        return await self.session.get(TrackedJob, tracked_job_id)

    async def get_job_by_user_and_source_url(
        self, *, user_id: str, source_job_url: str
    ) -> TrackedJob | None:
        result = await self.session.execute(
            select(TrackedJob)
            .where(
                TrackedJob.user_id == user_id,
                TrackedJob.source_job_url == source_job_url,
                TrackedJob.archived_at.is_(None),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_jobs_for_user(
        self,
        *,
        user_id: str,
        query: JobTrackerListQuery,
    ) -> list[TrackedJob]:
        statement = select(TrackedJob).where(TrackedJob.user_id == user_id)
        statement = self._apply_job_filters(statement=statement, query=query)
        statement = self._apply_job_sort(statement=statement, query=query)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_jobs(self, *, query: JobTrackerListQuery) -> list[TrackedJob]:
        statement = select(TrackedJob)
        statement = self._apply_job_filters(statement=statement, query=query)
        statement = self._apply_job_sort(statement=statement, query=query)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_job_activities(self, *, tracked_job_id: UUID) -> list[TrackedJobActivity]:
        result = await self.session.execute(
            select(TrackedJobActivity)
            .where(TrackedJobActivity.tracked_job_id == tracked_job_id)
            .order_by(desc(TrackedJobActivity.created_at))
        )
        return list(result.scalars().all())

    async def list_activities_for_user(self, *, user_id: str) -> list[TrackedJobActivity]:
        result = await self.session.execute(
            select(TrackedJobActivity)
            .where(TrackedJobActivity.user_id == user_id)
            .order_by(desc(TrackedJobActivity.created_at))
        )
        return list(result.scalars().all())

    async def list_job_contacts(self, *, tracked_job_id: UUID) -> list[TrackedJobContact]:
        result = await self.session.execute(
            select(TrackedJobContact)
            .where(TrackedJobContact.tracked_job_id == tracked_job_id)
            .order_by(desc(TrackedJobContact.created_at))
        )
        return list(result.scalars().all())

    async def get_activity_by_id(
        self, *, tracked_job_id: UUID, activity_id: UUID
    ) -> TrackedJobActivity | None:
        result = await self.session.execute(
            select(TrackedJobActivity)
            .where(
                TrackedJobActivity.id == activity_id,
                TrackedJobActivity.tracked_job_id == tracked_job_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    def add_job(self, **kwargs) -> TrackedJob:
        tracked_job = TrackedJob(**kwargs)
        self.session.add(tracked_job)
        return tracked_job

    def add_activity(self, **kwargs) -> TrackedJobActivity:
        activity = TrackedJobActivity(**kwargs)
        self.session.add(activity)
        return activity

    def add_contact(self, **kwargs) -> TrackedJobContact:
        contact = TrackedJobContact(**kwargs)
        self.session.add(contact)
        return contact

    async def recalculate_next_follow_up_at(self, *, tracked_job_id: UUID) -> datetime | None:
        tracked_job = await self.get_job_by_id(tracked_job_id=tracked_job_id)
        if tracked_job is None:
            return None
        result = await self.session.execute(
            select(TrackedJobActivity)
            .where(
                TrackedJobActivity.tracked_job_id == tracked_job_id,
                TrackedJobActivity.activity_type == TRACKED_JOB_ACTIVITY_FOLLOW_UP,
                TrackedJobActivity.completed_at.is_(None),
                TrackedJobActivity.due_at.is_not(None),
            )
            .order_by(TrackedJobActivity.due_at.asc())
            .limit(1)
        )
        activity = result.scalar_one_or_none()
        tracked_job.next_follow_up_at = activity.due_at if activity is not None else None
        return tracked_job.next_follow_up_at

    def _apply_job_filters(self, *, statement: Select, query: JobTrackerListQuery) -> Select:
        if query.archived:
            statement = statement.where(TrackedJob.archived_at.is_not(None))
        else:
            statement = statement.where(TrackedJob.archived_at.is_(None))

        if query.status is not None:
            statement = statement.where(TrackedJob.status == query.status)
        if query.site is not None:
            statement = statement.where(TrackedJob.site == query.site)
        if query.priority is not None:
            statement = statement.where(TrackedJob.priority == query.priority)
        if query.has_follow_up is True:
            statement = statement.where(TrackedJob.next_follow_up_at.is_not(None))
        if query.has_follow_up is False:
            statement = statement.where(TrackedJob.next_follow_up_at.is_(None))
        if query.search:
            pattern = f"%{query.search.strip()}%"
            statement = statement.where(
                or_(
                    TrackedJob.title.ilike(pattern),
                    TrackedJob.company_name.ilike(pattern),
                    TrackedJob.location.ilike(pattern),
                    TrackedJob.site.ilike(pattern),
                )
            )
        return statement

    def _apply_job_sort(self, *, statement: Select, query: JobTrackerListQuery) -> Select:
        if query.sort == TRACKED_JOB_SORT_DEADLINE_AT:
            return statement.order_by(desc(TrackedJob.deadline_at), desc(TrackedJob.updated_at))
        if query.sort == TRACKED_JOB_SORT_NEXT_FOLLOW_UP_AT:
            return statement.order_by(
                desc(TrackedJob.next_follow_up_at), desc(TrackedJob.updated_at)
            )
        if query.sort == TRACKED_JOB_SORT_APPLIED_AT:
            return statement.order_by(desc(TrackedJob.applied_at), desc(TrackedJob.updated_at))
        return statement.order_by(desc(TrackedJob.updated_at))
