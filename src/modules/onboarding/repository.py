from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.onboarding.models import OnboardingSession

ACTIVE_ONBOARDING_STATUSES = (
    "draft",
    "extracting",
    "awaiting_clarification",
    "clarifying",
    "verifying",
    "planning",
    "awaiting_confirmation",
)


class OnboardingSessionsRepository:
    """Database access layer for onboarding sessions."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_active_for_user(self, *, user_id: str) -> OnboardingSession | None:
        """Return the latest active onboarding session for a user."""
        result = await self.session.execute(
            select(OnboardingSession)
            .where(
                OnboardingSession.user_id == user_id,
                OnboardingSession.status.in_(ACTIVE_ONBOARDING_STATUSES),
            )
            .order_by(desc(OnboardingSession.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, *, onboarding_session_id: UUID) -> OnboardingSession | None:
        """Fetch an onboarding session by identifier."""
        return await self.session.get(OnboardingSession, onboarding_session_id)

    def add(
        self,
        *,
        user_id: str,
        status: str,
        current_step: str,
        superseded_by_session_id: UUID | None = None,
    ) -> OnboardingSession:
        """Create and stage an onboarding session."""
        onboarding_session = OnboardingSession(
            user_id=user_id,
            status=status,
            current_step=current_step,
            superseded_by_session_id=superseded_by_session_id,
        )
        self.session.add(onboarding_session)
        return onboarding_session
