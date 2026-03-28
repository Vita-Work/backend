from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.resume_intakes.models import ResumeIntake


class ResumeIntakesRepository:
    """Database access for temporary resume intakes."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    def add(
        self,
        *,
        intake_token_hash: str,
        status: str,
        claimed_user_id: str | None,
        storage_bucket: str,
        storage_key: str,
        storage_uri: str,
        cv_filename: str,
        cv_content_type: str,
        cv_extension: str,
        cv_size_bytes: int,
        cv_sha256: str,
        extraction_strategy: str,
        inline_text_characters: int | None,
        expires_at: datetime,
    ) -> ResumeIntake:
        intake = ResumeIntake(
            intake_token_hash=intake_token_hash,
            status=status,
            claimed_user_id=claimed_user_id,
            storage_bucket=storage_bucket,
            storage_key=storage_key,
            storage_uri=storage_uri,
            cv_filename=cv_filename,
            cv_content_type=cv_content_type,
            cv_extension=cv_extension,
            cv_size_bytes=cv_size_bytes,
            cv_sha256=cv_sha256,
            extraction_strategy=extraction_strategy,
            inline_text_characters=inline_text_characters,
            expires_at=expires_at,
        )
        self.session.add(intake)
        return intake

    async def get_by_token_hash(self, *, intake_token_hash: str) -> ResumeIntake | None:
        result = await self.session.execute(
            select(ResumeIntake).where(ResumeIntake.intake_token_hash == intake_token_hash).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_pending_for_user(self, *, user_id: str) -> ResumeIntake | None:
        result = await self.session.execute(
            select(ResumeIntake)
            .where(
                ResumeIntake.claimed_user_id == user_id,
                ResumeIntake.status == "claimed",
                ResumeIntake.consumed_at.is_(None),
            )
            .order_by(desc(ResumeIntake.claimed_at), desc(ResumeIntake.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
