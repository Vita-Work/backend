from __future__ import annotations

from src.modules.onboarding.models import OnboardingSession
from src.workflows.search_job.schemas import SearchJobContext


def build_search_job_context(*, onboarding_session: OnboardingSession) -> SearchJobContext:
    """Build the downstream search_job context from a completed search_setup session."""
    if not onboarding_session.search_strategy_summary:
        raise ValueError("Cannot build SearchJobContext without search_strategy_summary.")

    return SearchJobContext(
        user_id=onboarding_session.user_id,
        onboarding_session_id=str(onboarding_session.id),
        search_strategy_summary=onboarding_session.search_strategy_summary,
        hard_preferences=onboarding_session.hard_preferences or [],
        soft_preferences=onboarding_session.soft_preferences or [],
    )
