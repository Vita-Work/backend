import functools
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.url import get_async_database_url

engine = create_async_engine(
    get_async_database_url(),
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


def with_session[F: Callable[..., Awaitable]](func: F) -> F:
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


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Yield an async database session for FastAPI dependencies."""
    async with session_factory() as session:
        yield session


async def check_database_connection() -> None:
    """Raise when the application cannot reach the configured database."""
    async with session_factory() as session:
        await session.execute(text("SELECT 1"))
