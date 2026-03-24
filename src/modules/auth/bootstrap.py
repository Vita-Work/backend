from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.logger import get_logger
from src.modules.auth.security import hash_password, normalize_email, utcnow
from src.modules.users.repository import UsersRepository

logger = get_logger("auth.bootstrap")


async def bootstrap_admin_users(*, session: AsyncSession) -> None:
    settings = get_settings()
    try:
        admins_raw = json.loads(settings.admins)
    except json.JSONDecodeError:
        logger.error("admin_bootstrap_invalid_json")
        return

    if not isinstance(admins_raw, dict):
        logger.error("admin_bootstrap_invalid_shape")
        return

    users_repository = UsersRepository(session=session)
    for email, password in admins_raw.items():
        if (
            not isinstance(email, str)
            or not isinstance(password, str)
            or not email.strip()
            or not password
        ):
            logger.warning("admin_bootstrap_skipped_invalid_entry", email=str(email))
            continue

        normalized_email = normalize_email(email)
        existing_user = await users_repository.get_by_email(email=normalized_email)
        if existing_user is not None:
            logger.info(
                "admin_bootstrap_skipped_existing", email=normalized_email, user_id=existing_user.id
            )
            continue

        admin = users_repository.add(
            email=normalized_email,
            full_name=None,
            timezone="UTC",
            locale=None,
            role="admin",
            password_hash=hash_password(password),
            email_verified_at=utcnow(),
            status="active",
        )
        await session.flush()
        logger.info("admin_bootstrap_created", email=normalized_email, user_id=admin.id)

    await session.commit()
