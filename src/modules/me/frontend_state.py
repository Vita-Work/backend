from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.auth.security import utcnow
from src.modules.extraction.repository import ExtractionWorkflowRunsRepository
from src.modules.job_tracker.repository import TrackedJobsRepository
from src.modules.job_tracker.schemas import JobTrackerListQuery
from src.modules.onboarding.models import OnboardingSession
from src.modules.onboarding.repository import OnboardingSessionsRepository
from src.modules.onboarding.schemas import OnboardingThreadMessageResponse, OnboardingThreadResponse
from src.modules.search_jobs.repository import SearchJobWorkflowRunsRepository
from src.modules.users.models import User

AppPhase = Literal[
    "new_user",
    "upload_cv",
    "processing_cv",
    "onboarding_chat",
    "awaiting_confirmation",
    "searching_jobs",
    "results_ready",
]


@dataclass
class AppStateSnapshot:
    phase: AppPhase
    next_route: str
    needs_onboarding: bool
    has_active_onboarding_session: bool
    has_completed_onboarding: bool
    has_search_results: bool
    has_tracker_jobs: bool
    onboarding_session_id: UUID | None = None
    extraction_workflow_run_id: UUID | None = None
    search_job_workflow_run_id: UUID | None = None
    is_new_user: bool = False


async def build_app_state_snapshot(*, session: AsyncSession, user: User) -> AppStateSnapshot:
    onboarding_repository = OnboardingSessionsRepository(session=session)
    extraction_repository = ExtractionWorkflowRunsRepository(session=session)
    search_repository = SearchJobWorkflowRunsRepository(session=session)
    tracker_repository = TrackedJobsRepository(session=session)

    active_onboarding = await onboarding_repository.get_active_for_user(user_id=str(user.id))
    completed_onboarding = await onboarding_repository.get_latest_completed_for_user(
        user_id=str(user.id)
    )
    latest_extraction = await extraction_repository.get_latest_for_user(user_id=str(user.id))
    latest_search = await search_repository.get_latest_for_user(user_id=str(user.id))
    tracker_jobs = await tracker_repository.list_jobs_for_user(
        user_id=str(user.id),
        query=JobTrackerListQuery(),
    )

    has_tracker_jobs = bool(tracker_jobs)
    has_completed_onboarding = completed_onboarding is not None
    has_active_onboarding_session = active_onboarding is not None
    has_search_results = bool(
        latest_search is not None and latest_search.status == "completed" and latest_search.jobs
    )
    is_new_user = (
        not has_active_onboarding_session
        and not has_completed_onboarding
        and latest_extraction is None
        and not has_search_results
        and not has_tracker_jobs
    )

    if latest_search is not None and latest_search.status in {
        "queued",
        "planning",
        "searching",
        "deduping",
        "fetching_details",
        "unifying",
    }:
        return AppStateSnapshot(
            phase="searching_jobs",
            next_route="/searching",
            needs_onboarding=not has_completed_onboarding,
            has_active_onboarding_session=has_active_onboarding_session,
            has_completed_onboarding=has_completed_onboarding,
            has_search_results=has_search_results,
            has_tracker_jobs=has_tracker_jobs,
            onboarding_session_id=(
                active_onboarding.id
                if active_onboarding
                else completed_onboarding.id
                if completed_onboarding
                else None
            ),
            extraction_workflow_run_id=latest_extraction.id if latest_extraction else None,
            search_job_workflow_run_id=latest_search.id,
            is_new_user=is_new_user,
        )

    if has_search_results:
        return AppStateSnapshot(
            phase="results_ready",
            next_route="/jobs",
            needs_onboarding=False,
            has_active_onboarding_session=has_active_onboarding_session,
            has_completed_onboarding=has_completed_onboarding,
            has_search_results=True,
            has_tracker_jobs=has_tracker_jobs,
            onboarding_session_id=(
                completed_onboarding.id
                if completed_onboarding
                else active_onboarding.id
                if active_onboarding
                else None
            ),
            extraction_workflow_run_id=latest_extraction.id if latest_extraction else None,
            search_job_workflow_run_id=latest_search.id if latest_search else None,
            is_new_user=is_new_user,
        )

    if active_onboarding is not None:
        if active_onboarding.status in {"extracting"}:
            return AppStateSnapshot(
                phase="processing_cv",
                next_route="/onboarding/processing",
                needs_onboarding=True,
                has_active_onboarding_session=True,
                has_completed_onboarding=has_completed_onboarding,
                has_search_results=has_search_results,
                has_tracker_jobs=has_tracker_jobs,
                onboarding_session_id=active_onboarding.id,
                extraction_workflow_run_id=latest_extraction.id if latest_extraction else None,
                search_job_workflow_run_id=latest_search.id if latest_search else None,
                is_new_user=is_new_user,
            )
        if active_onboarding.status == "awaiting_confirmation":
            return AppStateSnapshot(
                phase="awaiting_confirmation",
                next_route="/onboarding/chat",
                needs_onboarding=True,
                has_active_onboarding_session=True,
                has_completed_onboarding=has_completed_onboarding,
                has_search_results=has_search_results,
                has_tracker_jobs=has_tracker_jobs,
                onboarding_session_id=active_onboarding.id,
                extraction_workflow_run_id=latest_extraction.id if latest_extraction else None,
                search_job_workflow_run_id=latest_search.id if latest_search else None,
                is_new_user=is_new_user,
            )
        if active_onboarding.status in {
            "awaiting_clarification",
            "clarifying",
            "verifying",
            "planning",
        }:
            return AppStateSnapshot(
                phase="onboarding_chat",
                next_route="/onboarding/chat",
                needs_onboarding=True,
                has_active_onboarding_session=True,
                has_completed_onboarding=has_completed_onboarding,
                has_search_results=has_search_results,
                has_tracker_jobs=has_tracker_jobs,
                onboarding_session_id=active_onboarding.id,
                extraction_workflow_run_id=latest_extraction.id if latest_extraction else None,
                search_job_workflow_run_id=latest_search.id if latest_search else None,
                is_new_user=is_new_user,
            )

    if latest_extraction is not None and latest_extraction.status in {"queued", "extracting"}:
        return AppStateSnapshot(
            phase="processing_cv",
            next_route="/onboarding/processing",
            needs_onboarding=True,
            has_active_onboarding_session=has_active_onboarding_session,
            has_completed_onboarding=has_completed_onboarding,
            has_search_results=has_search_results,
            has_tracker_jobs=has_tracker_jobs,
            onboarding_session_id=active_onboarding.id if active_onboarding else None,
            extraction_workflow_run_id=latest_extraction.id,
            search_job_workflow_run_id=latest_search.id if latest_search else None,
            is_new_user=is_new_user,
        )

    return AppStateSnapshot(
        phase="new_user" if is_new_user else "upload_cv",
        next_route="/auth/welcome" if is_new_user else "/onboarding/upload-cv",
        needs_onboarding=not has_completed_onboarding,
        has_active_onboarding_session=has_active_onboarding_session,
        has_completed_onboarding=has_completed_onboarding,
        has_search_results=has_search_results,
        has_tracker_jobs=has_tracker_jobs,
        onboarding_session_id=active_onboarding.id if active_onboarding else None,
        extraction_workflow_run_id=latest_extraction.id if latest_extraction else None,
        search_job_workflow_run_id=latest_search.id if latest_search else None,
        is_new_user=is_new_user,
    )


def build_onboarding_thread(
    *,
    onboarding_session: OnboardingSession,
    search_job_workflow_run_id: UUID | None,
) -> OnboardingThreadResponse:
    turns = onboarding_session.clarification_turns or []
    messages: list[OnboardingThreadMessageResponse] = []
    created_at = onboarding_session.created_at or utcnow()

    if onboarding_session.extracted_profile:
        messages.append(
            OnboardingThreadMessageResponse(
                id=f"{onboarding_session.id}:intro",
                role="agent",
                message_type="status_note",
                text="I reviewed your CV and I'm putting together your job search profile.",
                created_at=created_at,
            )
        )

    for index, turn in enumerate(turns):
        question = turn.get("question", "")
        answer = turn.get("answer", "")
        lower_question = question.lower()
        if lower_question == "plan confirmation feedback":
            messages.append(
                OnboardingThreadMessageResponse(
                    id=f"{onboarding_session.id}:confirmation-answer:{index}",
                    role="user",
                    message_type="confirmation_answer",
                    text=answer,
                    created_at=created_at,
                )
            )
            continue
        if lower_question == "conflict resolution feedback":
            messages.append(
                OnboardingThreadMessageResponse(
                    id=f"{onboarding_session.id}:conflict-answer:{index}",
                    role="user",
                    message_type="confirmation_answer",
                    text=answer,
                    created_at=created_at,
                )
            )
            continue
        messages.append(
            OnboardingThreadMessageResponse(
                id=f"{onboarding_session.id}:question:{index}",
                role="agent",
                message_type="clarification_question",
                text=question,
                created_at=created_at,
            )
        )
        messages.append(
            OnboardingThreadMessageResponse(
                id=f"{onboarding_session.id}:answer:{index}",
                role="user",
                message_type="user_answer",
                text=answer,
                created_at=created_at,
            )
        )

    if onboarding_session.pending_user_prompt:
        messages.append(
            OnboardingThreadMessageResponse(
                id=f"{onboarding_session.id}:pending",
                role="agent",
                message_type=(
                    onboarding_session.pending_user_prompt_type or "clarification_question"
                ),
                text=onboarding_session.pending_user_prompt,
                state="pending",
                created_at=onboarding_session.updated_at or created_at,
            )
        )

    input_mode = (
        "confirmation" if onboarding_session.status == "awaiting_confirmation" else "free_text"
    )
    confirmation_mode = "yes_no_with_optional_reason" if input_mode == "confirmation" else None

    return OnboardingThreadResponse(
        onboarding_session_id=onboarding_session.id,
        conversation_status=onboarding_session.status,
        input_mode=input_mode,
        confirmation_mode=confirmation_mode,
        messages=messages,
        search_job_workflow_run_id=search_job_workflow_run_id,
    )
