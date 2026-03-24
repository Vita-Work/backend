from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.engine import get_db_session
from src.modules.auth.repository import AuthRepository
from src.modules.auth.security import hash_session_token, utcnow
from src.modules.users.models import User
from src.modules.users.repository import UsersRepository

settings = get_settings()
db_session_dependency = Depends(get_db_session)


@dataclass
class AuthContext:
    user: User
    session_id: str
    role: str
    cookie_name: str


def _session_cookie_params() -> dict[str, object]:
    return {
        "httponly": True,
        "secure": settings.auth_cookie_secure,
        "samesite": "lax",
        "path": "/",
    }


def set_auth_cookie(*, response: Response, role: str, token: str) -> None:
    cookie_name = (
        settings.auth_cookie_name_admin if role == "admin" else settings.auth_cookie_name_user
    )
    other_cookie_name = (
        settings.auth_cookie_name_user if role == "admin" else settings.auth_cookie_name_admin
    )
    max_age = settings.auth_session_ttl_days * 24 * 60 * 60
    response.delete_cookie(other_cookie_name, path="/")
    response.set_cookie(
        key=cookie_name,
        value=token,
        max_age=max_age,
        **_session_cookie_params(),
    )


def clear_auth_cookie(*, response: Response, role: str | None = None) -> None:
    cookie_names = []
    if role is None:
        cookie_names = [settings.auth_cookie_name_user, settings.auth_cookie_name_admin]
    elif role == "admin":
        cookie_names = [settings.auth_cookie_name_admin]
    else:
        cookie_names = [settings.auth_cookie_name_user]

    for cookie_name in cookie_names:
        response.delete_cookie(cookie_name, path="/")


async def get_current_auth_context_optional(
    session: AsyncSession = db_session_dependency,
    user_cookie: str | None = Cookie(default=None, alias=settings.auth_cookie_name_user),
    admin_cookie: str | None = Cookie(default=None, alias=settings.auth_cookie_name_admin),
) -> AuthContext | None:
    cookies = []
    if admin_cookie:
        cookies.append((admin_cookie, "admin", settings.auth_cookie_name_admin))
    if user_cookie:
        cookies.append((user_cookie, "user", settings.auth_cookie_name_user))

    if not cookies:
        return None

    auth_repository = AuthRepository(session=session)
    users_repository = UsersRepository(session=session)
    now = utcnow()

    for raw_token, expected_role, cookie_name in cookies:
        auth_session = await auth_repository.get_session_by_token_hash(
            session_token_hash=hash_session_token(raw_token)
        )
        if auth_session is None:
            continue
        if auth_session.revoked_at is not None or auth_session.expires_at < now:
            continue
        if auth_session.role_snapshot != expected_role:
            continue

        user = await users_repository.get_by_id(user_id=UUID(auth_session.user_id))
        if user is None or user.status != "active" or user.role != expected_role:
            continue

        last_seen_at = auth_session.last_seen_at or auth_session.created_at
        if last_seen_at <= now - timedelta(seconds=settings.auth_session_touch_interval_seconds):
            auth_session.last_seen_at = now
            await session.commit()

        return AuthContext(
            user=user,
            session_id=str(auth_session.id),
            role=expected_role,
            cookie_name=cookie_name,
        )

    return None


optional_auth_context_dependency = Depends(get_current_auth_context_optional)


async def require_authenticated_user(
    context: AuthContext | None = optional_auth_context_dependency,
) -> AuthContext:
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required."
        )
    return context


authenticated_user_dependency = Depends(require_authenticated_user)


async def require_admin(
    context: AuthContext = authenticated_user_dependency,
) -> AuthContext:
    if context.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return context
