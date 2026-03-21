"""
Unified logging configuration with structlog.

Supports two modes:
- console: Pretty colored output for local development
- json: Structured JSON output for production (Loki/Grafana)

Usage:
    from src.logger import configure_logging, get_logger

    # Call once at startup
    configure_logging(log_format="console", log_level="DEBUG")

    # Get logger anywhere in the app (or keep using logging.getLogger)
    logger = get_logger("my_module")
    logger.info("message", user_id=123, action="create")
"""

import asyncio
import functools
import logging
import sys
import time
from contextvars import ContextVar
from typing import Any, Literal

import structlog
from structlog.types import Processor

# Context variable for request_id (set by middleware)
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_current_request_id() -> str | None:
    """
    Get current request_id from context.

    Checks both:
    1. request_id_var (set by RequestContextMiddleware for HTTP requests)
    2. structlog contextvars parent_request_id (set by background job middleware)

    Returns:
        Request ID string or None if not in a request context

    Usage:
        # In HTTP handler or background task
        req_id = get_current_request_id()
        headers = {"X-Request-ID": req_id} if req_id else {}
    """
    # First try request_id_var (HTTP requests)
    req_id = request_id_var.get()
    if req_id:
        return req_id

    # Then try structlog context (background tasks)
    try:
        ctx = structlog.contextvars.get_contextvars()
        return ctx.get("parent_request_id")
    except Exception:
        return None


# Track if logging has been configured
_logging_configured = False


def get_request_id() -> str | None:
    """Get current request_id from context variable."""
    return request_id_var.get()


def add_request_id(logger: logging.Logger, method_name: str, event_dict: dict) -> dict:
    """Add request_id from context variable to log event."""
    request_id = request_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def configure_logging(
    log_format: Literal["console", "json"] = "console",
    log_level: str = "DEBUG",
    service_name: str = "vita-backend",
) -> None:
    """
    Configure structlog with stdlib integration.

    Call this once at application startup.
    All existing logging.getLogger() calls will automatically use
    structlog formatting.

    Args:
        log_format: "console" for pretty dev output, "json" for Loki/prod
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        service_name: Service name to include in logs (for Loki filtering)
    """
    global _logging_configured

    if _logging_configured:
        return

    # Shared processors for both structlog and stdlib
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_request_id,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        # JSON renderer for production/Loki
        def add_service_name(logger, method_name, event_dict):
            event_dict["service"] = service_name
            return event_dict

        shared_processors.append(add_service_name)
        shared_processors.append(structlog.processors.format_exc_info)
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        # Pretty console renderer for development
        shared_processors.append(structlog.dev.set_exc_info)
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog processors
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Set levels for noisy third-party loggers
    for noisy_logger in [
        "httpx",
        "httpcore",
        "aiobotocore",
        "botocore",
        "python_multipart",
        "urllib3",
        "asyncio",
        "aiosqlite",
        "sqlalchemy.engine",
        "uvicorn.access",  # Disable duplicate access logs (we use RequestContextMiddleware)
        "uvicorn.error",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    _logging_configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (module name, e.g., "api", "worker")

    Returns:
        Configured structlog BoundLogger

    Usage:
        logger = get_logger("my_module")
        logger.info("user created", user_id=123)

        # With bound context (all subsequent logs will include user_id)
        log = logger.bind(user_id=123)
        log.info("action 1")
        log.info("action 2")
    """
    return structlog.get_logger(name)


# === DECORATORS ===


def log_function_call(func):
    """
    Decorator for logging function calls.
    Supports both sync and async functions.
    """
    logger = get_logger("function_calls")

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        logger.debug(
            "function_call_start",
            function=func.__name__,
            args_count=len(args),
            kwargs_keys=list(kwargs.keys()),
        )
        try:
            result = await func(*args, **kwargs)
            logger.debug("function_call_success", function=func.__name__)
            return result
        except Exception as e:
            logger.error(
                "function_call_error",
                function=func.__name__,
                error=str(e),
                exc_info=True,
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        logger.debug(
            "function_call_start",
            function=func.__name__,
            args_count=len(args),
            kwargs_keys=list(kwargs.keys()),
        )
        try:
            result = func(*args, **kwargs)
            logger.debug("function_call_success", function=func.__name__)
            return result
        except Exception as e:
            logger.error(
                "function_call_error",
                function=func.__name__,
                error=str(e),
                exc_info=True,
            )
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def log_performance(func):
    """
    Decorator for measuring function performance.
    Supports both sync and async functions.
    """
    logger = get_logger("performance")

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            duration = time.perf_counter() - start_time
            logger.info(
                "function_performance",
                function=func.__name__,
                duration_seconds=round(duration, 4),
                status="success",
            )
            return result
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                "function_performance",
                function=func.__name__,
                duration_seconds=round(duration, 4),
                status="error",
                error=str(e),
                exc_info=True,
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start_time
            logger.info(
                "function_performance",
                function=func.__name__,
                duration_seconds=round(duration, 4),
                status="success",
            )
            return result
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(
                "function_performance",
                function=func.__name__,
                duration_seconds=round(duration, 4),
                status="error",
                error=str(e),
                exc_info=True,
            )
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


def log_redis_operation(
    operation: str,
    channel: str | None = None,
    data: Any = None,
) -> None:
    """Log Redis operations with structured data."""
    logger = get_logger("redis")
    logger.info(
        "redis_operation",
        operation=operation,
        channel=channel,
        data_type=type(data).__name__ if data else None,
        data_size=len(str(data)) if data else 0,
    )
