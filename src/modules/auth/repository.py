from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.auth.models import AuthEmailChallenge, AuthSession


class AuthRepository:
    """Database access for auth challenges and sessions."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def get_latest_challenge(self, *, email: str) -> AuthEmailChallenge | None:
        result = await self.session.execute(
            select(AuthEmailChallenge)
            .where(AuthEmailChallenge.email == email)
            .order_by(desc(AuthEmailChallenge.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_recent_challenges(self, *, email: str, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count(AuthEmailChallenge.id)).where(
                AuthEmailChallenge.email == email,
                AuthEmailChallenge.created_at >= since,
            )
        )
        return int(result.scalar_one() or 0)

    async def invalidate_active_challenges(self, *, email: str) -> None:
        result = await self.session.execute(
            select(AuthEmailChallenge).where(
                AuthEmailChallenge.email == email,
                AuthEmailChallenge.consumed_at.is_(None),
            )
        )
        for challenge in result.scalars().all():
            challenge.consumed_at = challenge.created_at

    def add_challenge(
        self,
        *,
        email: str,
        code_hash: str,
        expires_at: datetime,
        max_attempts: int,
        last_sent_at: datetime,
        request_ip: str | None,
        user_agent: str | None,
    ) -> AuthEmailChallenge:
        challenge = AuthEmailChallenge(
            email=email,
            code_hash=code_hash,
            expires_at=expires_at,
            max_attempts=max_attempts,
            last_sent_at=last_sent_at,
            request_ip=request_ip,
            user_agent=user_agent,
        )
        self.session.add(challenge)
        return challenge

    async def get_active_challenge_for_verification(
        self,
        *,
        email: str,
        now: datetime,
    ) -> AuthEmailChallenge | None:
        result = await self.session.execute(
            select(AuthEmailChallenge)
            .where(
                AuthEmailChallenge.email == email,
                AuthEmailChallenge.consumed_at.is_(None),
                AuthEmailChallenge.expires_at >= now,
            )
            .order_by(desc(AuthEmailChallenge.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_session_by_token_hash(self, *, session_token_hash: str) -> AuthSession | None:
        result = await self.session.execute(
            select(AuthSession).where(AuthSession.session_token_hash == session_token_hash).limit(1)
        )
        return result.scalar_one_or_none()

    def add_session(
        self,
        *,
        session_token_hash: str,
        user_id: str,
        role_snapshot: str,
        expires_at: datetime,
        created_ip: str | None,
        user_agent: str | None,
    ) -> AuthSession:
        auth_session = AuthSession(
            session_token_hash=session_token_hash,
            user_id=user_id,
            role_snapshot=role_snapshot,
            expires_at=expires_at,
            last_seen_at=datetime.now(UTC),
            created_ip=created_ip,
            user_agent=user_agent,
        )
        self.session.add(auth_session)
        return auth_session

    async def revoke_session(self, *, session_id: UUID, now: datetime) -> None:
        auth_session = await self.session.get(AuthSession, session_id)
        if auth_session is not None and auth_session.revoked_at is None:
            auth_session.revoked_at = now

    async def revoke_session_by_hash(self, *, session_token_hash: str, now: datetime) -> None:
        auth_session = await self.get_session_by_token_hash(session_token_hash=session_token_hash)
        if auth_session is not None and auth_session.revoked_at is None:
            auth_session.revoked_at = now

    async def list_sessions_for_user(self, *, user_id: str) -> list[AuthSession]:
        result = await self.session.execute(
            select(AuthSession)
            .where(AuthSession.user_id == user_id)
            .order_by(desc(AuthSession.created_at))
        )
        return list(result.scalars().all())
