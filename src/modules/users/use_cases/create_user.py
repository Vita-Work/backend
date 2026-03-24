from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import get_logger
from src.modules.users.models import User
from src.modules.users.repository import UsersRepository

logger = get_logger("users.create")


class UserEmailAlreadyExistsError(Exception):
    """Raised when attempting to create a user with a duplicate email."""


def _is_duplicate_email_error(exc: IntegrityError) -> bool:
    original_error = getattr(exc, "orig", None)
    sqlstate = getattr(original_error, "sqlstate", None) or getattr(original_error, "pgcode", None)
    detail = str(original_error or exc).lower()

    if sqlstate == "23505":
        return "email" in detail

    return "uq_users_email" in detail or "users_email_key" in detail


async def create_user(
    *,
    session: AsyncSession,
    email: str | None,
    full_name: str | None,
    timezone: str,
    locale: str | None,
    role: str = "user",
    password_hash: str | None = None,
    email_verified_at: datetime | None = None,
    status: str = "active",
) -> User:
    """Create a user in the database."""
    users_repository = UsersRepository(session=session)

    normalized_email = email.strip().lower() if email else None
    normalized_full_name = full_name.strip() if full_name else None
    normalized_timezone = timezone.strip() or "UTC"
    normalized_locale = locale.strip() if locale else None

    if normalized_email:
        existing_user = await users_repository.get_by_email(
            email=normalized_email,
        )
        if existing_user is not None:
            raise UserEmailAlreadyExistsError

    user = users_repository.add(
        email=normalized_email,
        full_name=normalized_full_name,
        timezone=normalized_timezone,
        locale=normalized_locale,
        role=role,
        password_hash=password_hash,
        email_verified_at=email_verified_at,
        status=status,
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if normalized_email and _is_duplicate_email_error(exc):
            raise UserEmailAlreadyExistsError from exc
        raise
    await session.refresh(user)

    logger.info("user_created", user_id=user.id)
    return user
