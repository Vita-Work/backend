from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.db.mixin import BaseMixin


class User(Base, BaseMixin):
    """Application user stored in the primary database."""

    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="UTC",
        server_default="UTC",
    )
    locale: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )
