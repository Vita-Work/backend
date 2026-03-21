from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.logger import configure_logging, get_logger
from src.middleware import RequestContextMiddleware

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
    try:
        yield
    finally:
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

    return app


app = create_app()
