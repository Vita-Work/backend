from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.logger import get_logger
from src.modules.auth.security import utcnow
from src.modules.billing.models import BillingAccessPass, BillingSubscription
from src.modules.billing.repository import BillingCreditLedgerRepository
from src.modules.billing.service import build_billing_entitlements, ensure_job_pack_allowances
from src.modules.job_ai.repository import TrackedJobAiRunsRepository
from src.modules.job_tracker.repository import TrackedJobsRepository
from src.modules.onboarding.repository import OnboardingSessionsRepository

logger = get_logger("job_ai.service")


@dataclass(frozen=True)
class TrackedJobApplicationContext:
    tracked_job_id: UUID
    onboarding_session_id: UUID
    context: dict[str, object]
    source_profile_hash: str
    source_job_hash: str


class JobAiRunNotAllowedError(RuntimeError):
    """Raised when the current user is not allowed to start an AI run."""


class JobAiRunEnqueueError(RuntimeError):
    """Raised when a background AI run cannot be enqueued."""


def compact_text(value: str | None, *, limit: int) -> str:
    if not value:
        return ""
    collapsed = " ".join(value.split())
    return collapsed[:limit]


async def build_tracked_job_application_context(
    *,
    session: AsyncSession,
    user_id: str,
    tracked_job_id: UUID,
) -> TrackedJobApplicationContext:
    tracked_job = await TrackedJobsRepository(session=session).get_job_by_id(
        tracked_job_id=tracked_job_id
    )
    if tracked_job is None or tracked_job.user_id != user_id:
        raise ValueError("Tracked job not found.")

    onboarding_session = await OnboardingSessionsRepository(
        session=session
    ).get_latest_completed_for_user(user_id=user_id)
    if onboarding_session is None:
        raise ValueError("No completed onboarding session found.")

    context = {
        "user_profile": compact_text(onboarding_session.extracted_profile, limit=4000),
        "verification_summary": compact_text(onboarding_session.verification_summary, limit=1200),
        "search_strategy_summary": compact_text(
            onboarding_session.search_strategy_summary, limit=1200
        ),
        "hard_preferences": list(onboarding_session.hard_preferences or []),
        "soft_preferences": list(onboarding_session.soft_preferences or []),
        "job_title": tracked_job.title,
        "company_name": tracked_job.company_name,
        "job_description": compact_text(tracked_job.description_snapshot, limit=6000),
        "job_skills": list(dict.fromkeys(tracked_job.skills_snapshot or []))[:25],
        "job_location": tracked_job.location or "",
        "job_employment_type": tracked_job.employment_type or "",
        "job_salary": tracked_job.salary_text or "",
        "why_apply_snapshot": compact_text(tracked_job.why_apply_snapshot, limit=1200),
        "fit_level": tracked_job.fit_level or "",
        "existing_notes_summary": compact_text(tracked_job.notes_summary, limit=1200),
    }

    profile_hash = _stable_hash(
        {
            "extracted_profile": onboarding_session.extracted_profile or "",
            "verification_summary": onboarding_session.verification_summary or "",
            "search_strategy_summary": onboarding_session.search_strategy_summary or "",
            "hard_preferences": onboarding_session.hard_preferences or [],
            "soft_preferences": onboarding_session.soft_preferences or [],
        }
    )
    job_hash = _stable_hash(
        {
            "title": tracked_job.title,
            "company_name": tracked_job.company_name,
            "description_snapshot": tracked_job.description_snapshot or "",
            "skills_snapshot": tracked_job.skills_snapshot or [],
            "why_apply_snapshot": tracked_job.why_apply_snapshot or "",
            "fit_level": tracked_job.fit_level or "",
        }
    )

    return TrackedJobApplicationContext(
        tracked_job_id=tracked_job_id,
        onboarding_session_id=onboarding_session.id,
        context=context,
        source_profile_hash=profile_hash,
        source_job_hash=job_hash,
    )


async def get_cached_match_gap_payload(
    *,
    session: AsyncSession,
    user_id: str,
    tracked_job_id: UUID,
    source_profile_hash: str,
    source_job_hash: str,
) -> dict[str, object] | None:
    cached = await TrackedJobAiRunsRepository(
        session=session
    ).get_latest_successful_for_job_with_hashes(
        user_id=user_id,
        tracked_job_id=tracked_job_id,
        run_type="match_gap",
        source_profile_hash=source_profile_hash,
        source_job_hash=source_job_hash,
    )
    if cached is None or not cached.payload:
        return None
    report = cached.payload.get("match_gap_report")
    if isinstance(report, dict):
        return report
    if cached.run_type == "match_gap":
        return cached.payload
    return None


async def queue_match_gap_run(
    *,
    session: AsyncSession,
    arq_redis: ArqRedis,
    user_id: str,
    tracked_job_id: UUID,
    subscription: BillingSubscription | None,
    access_pass: BillingAccessPass | None,
    parent_request_id: str | None = None,
    settings: Settings | None = None,
):
    config = settings or get_settings()
    entitlements = build_billing_entitlements(
        subscription=subscription,
        access_pass=access_pass,
        settings=config,
    )
    if not entitlements.can_run_match_gap_reports:
        raise JobAiRunNotAllowedError("Match / Gap Report is not available for this user.")

    repository = TrackedJobAiRunsRepository(session=session)
    application_context = await build_tracked_job_application_context(
        session=session,
        user_id=user_id,
        tracked_job_id=tracked_job_id,
    )
    cached = await repository.get_latest_successful_for_job_with_hashes(
        user_id=user_id,
        tracked_job_id=tracked_job_id,
        run_type="match_gap",
        source_profile_hash=application_context.source_profile_hash,
        source_job_hash=application_context.source_job_hash,
    )
    if cached is not None:
        return cached

    if entitlements.access_plan_code == "free":
        successful_runs = await repository.count_successful_runs_for_user(
            user_id=user_id,
            run_type="match_gap",
        )
        if successful_runs >= (config.billing_free_match_gap_limit or 0):
            raise JobAiRunNotAllowedError("Free Match / Gap Report limit reached.")

    run = repository.add_run(
        user_id=user_id,
        tracked_job_id=tracked_job_id,
        run_type="match_gap",
        status="queued",
        credit_cost=0,
        source_onboarding_session_id=application_context.onboarding_session_id,
        source_profile_hash=application_context.source_profile_hash,
        source_job_hash=application_context.source_job_hash,
        payload={},
    )
    await session.flush()
    await session.commit()
    await session.refresh(run)
    return await _enqueue_job_ai_run(
        session=session,
        arq_redis=arq_redis,
        run_id=run.id,
        user_id=user_id,
        parent_request_id=parent_request_id,
    )


async def queue_job_pack_run(
    *,
    session: AsyncSession,
    arq_redis: ArqRedis,
    user_id: str,
    tracked_job_id: UUID,
    subscription: BillingSubscription | None,
    access_pass: BillingAccessPass | None,
    parent_request_id: str | None = None,
    settings: Settings | None = None,
):
    config = settings or get_settings()
    entitlements = build_billing_entitlements(
        subscription=subscription,
        access_pass=access_pass,
        settings=config,
    )
    if not entitlements.can_generate_job_packs:
        raise JobAiRunNotAllowedError("Tailor Pack is not available for this user.")

    credit_repository = BillingCreditLedgerRepository(session=session)
    remaining_credits = await ensure_job_pack_allowances(
        user_id=user_id,
        subscription=subscription,
        access_pass=access_pass,
        credit_repository=credit_repository,
        settings=config,
    )
    if remaining_credits < 1:
        raise JobAiRunNotAllowedError("No Tailor Pack credits available.")

    repository = TrackedJobAiRunsRepository(session=session)
    application_context = await build_tracked_job_application_context(
        session=session,
        user_id=user_id,
        tracked_job_id=tracked_job_id,
    )
    run = repository.add_run(
        user_id=user_id,
        tracked_job_id=tracked_job_id,
        run_type="job_pack",
        status="queued",
        credit_cost=1,
        source_onboarding_session_id=application_context.onboarding_session_id,
        source_profile_hash=application_context.source_profile_hash,
        source_job_hash=application_context.source_job_hash,
        payload={},
    )
    await session.flush()
    credit_repository.add_entry(
        user_id=user_id,
        credit_type="job_pack",
        delta=-1,
        entry_type="spend_reserved",
        tracked_job_id=str(tracked_job_id),
        ai_run_id=str(run.id),
        meta={"reason": "job_pack_run_reserved"},
    )
    await session.commit()
    await session.refresh(run)
    return await _enqueue_job_ai_run(
        session=session,
        arq_redis=arq_redis,
        run_id=run.id,
        user_id=user_id,
        parent_request_id=parent_request_id,
    )


async def commit_job_pack_reservation(
    *,
    session: AsyncSession,
    run_id: UUID,
    user_id: str,
    tracked_job_id: UUID,
) -> None:
    credit_repository = BillingCreditLedgerRepository(session=session)
    existing = await credit_repository.find_entry_by_ai_run_and_type(
        ai_run_id=str(run_id),
        entry_type="spend_committed",
    )
    if existing is not None:
        return
    credit_repository.add_entry(
        user_id=user_id,
        credit_type="job_pack",
        delta=0,
        entry_type="spend_committed",
        tracked_job_id=str(tracked_job_id),
        ai_run_id=str(run_id),
        meta={"reason": "job_pack_run_committed"},
    )


async def reverse_job_pack_reservation(
    *,
    session: AsyncSession,
    run_id: UUID,
    user_id: str,
    tracked_job_id: UUID,
) -> None:
    credit_repository = BillingCreditLedgerRepository(session=session)
    committed = await credit_repository.find_entry_by_ai_run_and_type(
        ai_run_id=str(run_id),
        entry_type="spend_committed",
    )
    if committed is not None:
        return
    existing = await credit_repository.find_entry_by_ai_run_and_type(
        ai_run_id=str(run_id),
        entry_type="spend_reversed",
    )
    if existing is not None:
        return
    reserved = await credit_repository.find_entry_by_ai_run_and_type(
        ai_run_id=str(run_id),
        entry_type="spend_reserved",
    )
    if reserved is None:
        return
    credit_repository.add_entry(
        user_id=user_id,
        credit_type="job_pack",
        delta=1,
        entry_type="spend_reversed",
        tracked_job_id=str(tracked_job_id),
        ai_run_id=str(run_id),
        meta={"reason": "job_pack_run_failed"},
    )


async def _enqueue_job_ai_run(
    *,
    session: AsyncSession,
    arq_redis: ArqRedis,
    run_id: UUID,
    user_id: str,
    parent_request_id: str | None,
):
    repository = TrackedJobAiRunsRepository(session=session)
    run = await repository.get_by_id(run_id=run_id)
    if run is None:
        raise JobAiRunEnqueueError("Tracked job AI run not found after creation.")

    try:
        job = await arq_redis.enqueue_job(
            "process_tracked_job_ai_run",
            str(run.id),
            _job_id=str(run.id),
            _parent_request_id=parent_request_id,
            _user_id=user_id,
        )
        if job is None:
            logger.info("job_ai_run_reused_existing_job", run_id=run.id, user_id=user_id)
            return run
    except Exception as exc:
        if run.run_type == "job_pack":
            await reverse_job_pack_reservation(
                session=session,
                run_id=run.id,
                user_id=user_id,
                tracked_job_id=run.tracked_job_id,
            )
        run.status = "failed"
        run.error_message = "Failed to enqueue tracked job AI run."
        run.completed_at = utcnow()
        await session.commit()
        logger.error(
            "job_ai_run_enqueue_failed",
            run_id=run.id,
            user_id=user_id,
            error=str(exc),
            exc_info=True,
        )
        raise JobAiRunEnqueueError("Failed to enqueue tracked job AI run.") from exc

    logger.info("job_ai_run_queued", run_id=run.id, user_id=user_id, run_type=run.run_type)
    return run


def _stable_hash(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
