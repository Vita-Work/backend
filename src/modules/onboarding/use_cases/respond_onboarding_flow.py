from __future__ import annotations

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.onboarding.models import OnboardingSession
from src.modules.onboarding.use_cases.advance_onboarding_flow import advance_onboarding_flow
from src.modules.search_jobs.use_cases.queue_search_job_workflow import queue_search_job_workflow


async def respond_onboarding_flow(
    *,
    session: AsyncSession,
    arq_redis: ArqRedis,
    user_id: str,
    answer: str,
) -> OnboardingSession:
    onboarding_session = await advance_onboarding_flow(
        session=session,
        user_id=user_id,
        answer=answer,
    )
    if onboarding_session.status == "completed":
        await queue_search_job_workflow(
            session=session,
            arq_redis=arq_redis,
            user_id=user_id,
        )

    return onboarding_session
