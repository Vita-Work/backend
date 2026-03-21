from uuid import UUID

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.mixin import BaseMixin


class ExtractionWorkflowRun(Base, BaseMixin):
    """Persisted extraction workflow execution state."""

    __tablename__ = "extraction_workflow_runs"

    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    onboarding_session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )

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

    extracted_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_info: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    preference_hints: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
