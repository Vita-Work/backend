import functools
import time

import structlog

from src.logger import get_logger

logger = get_logger("arq.job")


def arq_job_middleware(func):
    """
    Wrap an ARQ job with consistent logging and context propagation.
    """

    @functools.wraps(func)
    async def wrapper(ctx, *args, **kwargs):
        job_id = ctx.get("job_id")
        parent_request_id = kwargs.pop("_parent_request_id", None)
        user_id = kwargs.pop("_user_id", None)

        structlog.contextvars.bind_contextvars(
            job_id=job_id, parent_request_id=parent_request_id, user_id=user_id
        )

        start_time = time.perf_counter()

        logger.info("job_started", function=func.__name__)

        try:
            result = await func(ctx, *args, **kwargs)

            duration = time.perf_counter() - start_time

            logger.info(
                "job_completed",
                function=func.__name__,
                status="success",
                duration_seconds=round(duration, 4),
            )

            return result

        except Exception as exc:
            duration = time.perf_counter() - start_time

            logger.error(
                "job_failed",
                function=func.__name__,
                status="failed",
                duration_seconds=round(duration, 4),
                error=str(exc),
                exc_info=True,
            )
            raise

        finally:
            structlog.contextvars.clear_contextvars()

    return wrapper
