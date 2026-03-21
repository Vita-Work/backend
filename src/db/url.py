import os


def _read_database_url_from_environment() -> str | None:
    return os.getenv("DATABASE_URL") or os.getenv("DATABASE_DSN")


def get_database_url() -> str:
    """Return the configured database URL from settings or environment."""
    try:
        from src.config import get_settings
    except ModuleNotFoundError as err:
        database_url = _read_database_url_from_environment()
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

    environment_database_url = _read_database_url_from_environment()
    if environment_database_url:
        return environment_database_url

    raise RuntimeError("Settings must define `connection_string` for database access.")


def get_async_database_url() -> str:
    """Return a database URL suitable for SQLAlchemy async engines."""
    database_url = get_database_url()

    if database_url.startswith("postgresql+asyncpg://"):
        return database_url

    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)

    return database_url


def get_sync_database_url() -> str:
    """Return a database URL suitable for sync database tools like Alembic."""
    database_url = get_database_url()

    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)

    return database_url
