import functools
import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _get_database_url() -> str:
    try:
        from src.config import get_settings
    except ModuleNotFoundError as err:
        database_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_DSN")
        if database_url:
            return database_url

        raise RuntimeError(
            "Database URL is not configured. Define DATABASE_URL (or DATABASE_DSN), "
            "or add src.config.get_settings()."
        ) from err

    settings = get_settings()
    database_url = getattr(settings, "connection_string", None)
    if database_url:
        return database_url

    raise RuntimeError("Settings must define `connection_string` for database access.")


engine = create_async_engine(
    _get_database_url(),
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)

session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


F = TypeVar("F", bound=Callable[..., Awaitable])


def with_session(func: F) -> F:
    """
    Open a new AsyncSession and inject it into `session` when one was not passed.

    Transaction boundaries stay explicit at the call site: no implicit commit or rollback.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):  # type: ignore[override]
        if "session" in kwargs and isinstance(kwargs["session"], AsyncSession):
            return await func(*args, **kwargs)

        async with session_factory() as session:
            kwargs["session"] = session
            return await func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session:
        yield session
