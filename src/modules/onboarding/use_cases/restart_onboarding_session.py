from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.onboarding.models import OnboardingSession
from src.modules.onboarding.repository import OnboardingSessionsRepository


async def restart_onboarding_session(
    *,
    session: AsyncSession,
    user_id: str,
) -> OnboardingSession:
    """Supersede the current active onboarding session and create a fresh draft session."""
    repository = OnboardingSessionsRepository(session=session)
    active_session = await repository.get_active_for_user(user_id=user_id)

    if active_session is not None:
        active_session.status = "superseded"
        active_session.pending_user_prompt = None
        active_session.pending_user_prompt_type = None
        await session.flush()

    new_session = repository.add(
        user_id=user_id,
        status="draft",
        current_step="extraction",
    )
    await session.flush()

    if active_session is not None:
        active_session.superseded_by_session_id = new_session.id

    await session.commit()
    await session.refresh(new_session)
    return new_session
