from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base
from src.db.mixin import BaseMixin


class ResumeIntake(Base, BaseMixin):
    """Temporary anonymous resume upload that can be claimed after auth."""

    __tablename__ = "resume_intakes"

    intake_token_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uploaded",
        server_default="uploaded",
        index=True,
    )
    claimed_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    storage_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)

    cv_filename: Mapped[str] = mapped_column(Text, nullable=False)
    cv_content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    cv_extension: Mapped[str] = mapped_column(String(16), nullable=False)
    cv_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    cv_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    inline_text_characters: Mapped[int | None] = mapped_column(Integer, nullable=True)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
