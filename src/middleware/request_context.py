import time
import uuid
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.logger import get_logger, request_id_var

logger = get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Add request context, request logging, and correlation headers.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_var.set(request_id)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        request.state.request_id = request_id
        start_time = time.perf_counter()

        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) if request.query_params else None,
            client_ip=request.client.host if request.client else None,
        )

        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time

            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_seconds=round(duration, 4),
            )

            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            duration = time.perf_counter() - start_time

            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_seconds=round(duration, 4),
                error=str(exc),
                exc_info=True,
            )
            raise
        finally:
            request_id_var.set(None)
            structlog.contextvars.clear_contextvars()
