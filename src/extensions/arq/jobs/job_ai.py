from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import with_session
from src.extensions.arq.middleware import arq_job_middleware
from src.logger import get_logger
from src.modules.auth.security import utcnow
from src.modules.job_ai.repository import TrackedJobAiRunsRepository
from src.modules.job_ai.service import (
    build_tracked_job_application_context,
    commit_job_pack_reservation,
    get_cached_match_gap_payload,
    reverse_job_pack_reservation,
)
from src.workflows.job_application.graph import get_job_application_graph

logger = get_logger("arq.jobs.job_ai")


@arq_job_middleware
@with_session
async def process_tracked_job_ai_run(
    ctx: dict,
    run_id: str,
    *,
    session: AsyncSession,
) -> None:
    _ = ctx
    repository = TrackedJobAiRunsRepository(session=session)
    run = await repository.get_by_id(run_id=UUID(run_id))
    if run is None:
        raise RuntimeError(f"Tracked job AI run not found: {run_id}")

    run.status = "running"
    run.started_at = utcnow()
    run.completed_at = None
    run.error_message = None
    await session.commit()

    try:
        application_context = await build_tracked_job_application_context(
            session=session,
            user_id=run.user_id,
            tracked_job_id=run.tracked_job_id,
        )
        cached_match_gap_report = await get_cached_match_gap_payload(
            session=session,
            user_id=run.user_id,
            tracked_job_id=run.tracked_job_id,
            source_profile_hash=application_context.source_profile_hash,
            source_job_hash=application_context.source_job_hash,
        )

        graph = get_job_application_graph()
        result = await graph.ainvoke(
            {
                "run_id": str(run.id),
                "run_type": run.run_type,
                "user_id": run.user_id,
                "tracked_job_id": str(run.tracked_job_id),
                "context": application_context.context,
                "source_profile_hash": application_context.source_profile_hash,
                "source_job_hash": application_context.source_job_hash,
                "cached_match_gap_report": cached_match_gap_report,
            }
        )
    except Exception as exc:
        if run.run_type == "job_pack":
            await reverse_job_pack_reservation(
                session=session,
                run_id=run.id,
                user_id=run.user_id,
                tracked_job_id=run.tracked_job_id,
            )
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = utcnow()
        await session.commit()
        logger.error(
            "tracked_job_ai_run_failed",
            run_id=run.id,
            user_id=run.user_id,
            run_type=run.run_type,
            error=str(exc),
            exc_info=True,
        )
        raise

    run.status = "completed"
    run.source_onboarding_session_id = application_context.onboarding_session_id
    run.source_profile_hash = application_context.source_profile_hash
    run.source_job_hash = application_context.source_job_hash
    run.payload = dict(result.get("final_payload") or {})
    run.completed_at = utcnow()
    run.error_message = None
    if run.run_type == "job_pack":
        await commit_job_pack_reservation(
            session=session,
            run_id=run.id,
            user_id=run.user_id,
            tracked_job_id=run.tracked_job_id,
        )
    await session.commit()

    logger.info(
        "tracked_job_ai_run_completed",
        run_id=run.id,
        user_id=run.user_id,
        run_type=run.run_type,
    )
