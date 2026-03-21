from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.onboarding.models import OnboardingSession
from src.modules.onboarding.repository import OnboardingSessionsRepository


async def get_active_onboarding_session(
    *,
    session: AsyncSession,
    user_id: str,
) -> OnboardingSession | None:
    """Return the active onboarding session for a user, if one exists."""
    repository = OnboardingSessionsRepository(session=session)
    return await repository.get_active_for_user(user_id=user_id)
