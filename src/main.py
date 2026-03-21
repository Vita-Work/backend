from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.db.engine import check_database_connection
from src.logger import configure_logging, get_logger
from src.middleware import RequestContextMiddleware
from src.modules.extraction.routes import router as extraction_router
from src.modules.onboarding.routes import router as onboarding_router
from src.modules.users.routes import router as users_router
from src.workflows.search_setup.runtime import (
    start_search_setup_runtime,
    stop_search_setup_runtime,
)

settings = get_settings()

configure_logging(
    log_format=settings.effective_log_format,
    log_level=settings.effective_log_level,
    service_name=settings.service_name,
)

logger = get_logger("vita.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log application startup and shutdown lifecycle events."""
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        environment=settings.environment,
    )
    await start_search_setup_runtime()
    try:
        yield
    finally:
        arq_redis = getattr(app.state, "arq_redis", None)
        if arq_redis is not None:
            await arq_redis.aclose()
        await stop_search_setup_runtime()
        logger.info("application_shutdown_complete", app_name=settings.app_name)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        lifespan=lifespan,
        title=settings.app_name,
        description="Backend API for Vita.",
        version=settings.app_version,
    )

    app.add_middleware(RequestContextMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict[str, str]:
        """Return a lightweight API identification payload."""
        return {"message": settings.app_name}

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Return a basic health probe response."""
        return {"status": "ok"}

    @app.get("/health/db")
    async def database_health_check() -> dict[str, str]:
        """Return a database connectivity probe response."""
        try:
            await check_database_connection()
        except Exception as exc:
            logger.error("database_health_check_failed", error=str(exc), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is unavailable.",
            ) from exc

        return {"status": "ok", "database": "ok"}

    app.include_router(users_router)
    app.include_router(extraction_router)
    app.include_router(onboarding_router)

    return app


app = create_app()
