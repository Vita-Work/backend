from arq import cron
from arq.connections import RedisSettings
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from src.config import get_settings
from src.extensions.arq.jobs.billing import enqueue_due_monitoring_runs
from src.extensions.arq.jobs.extraction import process_cv_extraction_workflow
from src.extensions.arq.jobs.search_jobs import process_search_job_workflow
from src.logger import configure_logging, get_logger
from src.workflows.search_setup.runtime import (
    start_search_setup_runtime,
    stop_search_setup_runtime,
)

settings = get_settings()

MAX_JOBS = settings.arq_max_jobs
MAX_TRIES = settings.arq_max_tries
JOB_TIMEOUT = settings.arq_job_timeout
KEEP_RESULT = settings.arq_keep_result

REDIS_SETTINGS = RedisSettings(
    host=settings.redis_host,
    port=settings.redis_port,
    database=settings.redis_db,
    password=settings.redis_password,
    conn_timeout=settings.redis_conn_timeout_seconds,
    conn_retries=settings.redis_conn_retries,
    conn_retry_delay=settings.redis_conn_retry_delay_seconds,
    max_connections=settings.redis_max_connections,
    retry_on_timeout=settings.redis_retry_on_timeout,
    retry_on_error=[RedisConnectionError, RedisTimeoutError],
)

_arq_initialized = False
logger = get_logger("arq.worker")


def init_arq_worker() -> None:
    """Configure shared logging for ARQ workers once at startup."""
    global _arq_initialized

    if _arq_initialized:
        return

    configure_logging(
        log_format=settings.effective_log_format,
        log_level=settings.effective_log_level,
        service_name=f"{settings.service_name}-worker",
    )
    _arq_initialized = True


async def on_startup(ctx: dict) -> None:
    """Initialize shared worker context before processing jobs."""
    init_arq_worker()
    ctx["settings"] = settings
    await start_search_setup_runtime()
    logger.info("worker_starting", service_name=f"{settings.service_name}-worker")


async def on_shutdown(ctx: dict) -> None:
    """Log worker shutdown for observability."""
    _ = ctx
    await stop_search_setup_runtime()
    logger.info("worker_shutdown_complete", service_name=f"{settings.service_name}-worker")


class WorkerSettings:
    """Default ARQ worker settings for the project template."""

    functions = [
        process_cv_extraction_workflow,
        process_search_job_workflow,
        enqueue_due_monitoring_runs,
    ]
    cron_jobs = [
        cron(
            enqueue_due_monitoring_runs,
            name="enqueue_due_monitoring_runs",
            minute=5,
            second=0,
            microsecond=0,
            unique=True,
        )
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = REDIS_SETTINGS
    max_jobs = MAX_JOBS
    max_tries = MAX_TRIES
    job_timeout = JOB_TIMEOUT
    keep_result = KEEP_RESULT
