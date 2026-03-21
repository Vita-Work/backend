from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.users.models import User


class UsersRepository:
    """Database access layer for users."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, *, user_id: UUID) -> User | None:
        """Fetch a single user by identifier."""
        return await self.session.get(User, user_id)

    async def get_by_email(self, *, email: str) -> User | None:
        """Fetch a single user by email address."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    def add(
        self,
        *,
        email: str | None,
        full_name: str | None,
        timezone: str,
        locale: str | None,
    ) -> User:
        """Create and stage a user ORM object in the current session."""
        user = User(
            email=email,
            full_name=full_name,
            timezone=timezone,
            locale=locale,
        )
        self.session.add(user)
        return user
