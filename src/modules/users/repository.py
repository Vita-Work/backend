from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, select
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

    async def list_all(self) -> list[User]:
        """Return users ordered by newest first."""
        result = await self.session.execute(select(User).order_by(desc(User.created_at)))
        return list(result.scalars().all())

    def add(
        self,
        *,
        email: str | None,
        full_name: str | None,
        timezone: str,
        locale: str | None,
        role: str = "user",
        email_verified_at: datetime | None = None,
        password_hash: str | None = None,
        status: str = "active",
    ) -> User:
        """Create and stage a user ORM object in the current session."""
        user = User(
            email=email,
            full_name=full_name,
            timezone=timezone,
            locale=locale,
            role=role,
            email_verified_at=email_verified_at,
            password_hash=password_hash,
            status=status,
        )
        self.session.add(user)
        return user
