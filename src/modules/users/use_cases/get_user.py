from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.users.models import User
from src.modules.users.repository import UsersRepository


async def get_user(*, session: AsyncSession, user_id: UUID) -> User | None:
    """Return a user by identifier."""
    users_repository = UsersRepository(session=session)
    return await users_repository.get_by_id(user_id=user_id)
