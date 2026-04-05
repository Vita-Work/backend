from __future__ import annotations

from arq.connections import ArqRedis

from src.config import get_settings
from src.logger import get_logger

logger = get_logger("extraction.provider_health")

_FAILURE_COUNT_KEY = "vita:cv_extraction:provider_failure_count"
_DEGRADED_KEY = "vita:cv_extraction:provider_degraded"
_DEGRADATION_ERROR_CODES = frozenset(
    {"provider_quota_exhausted", "provider_timeout", "provider_unavailable"}
)


class CvExtractionProviderUnavailableError(RuntimeError):
    """Raised when extraction should be rejected before queueing."""


async def ensure_cv_extraction_provider_available(*, arq_redis: ArqRedis) -> None:
    """Fail fast when the extraction provider is in a short degraded window."""
    degraded_error_code = await arq_redis.get(_DEGRADED_KEY)
    if degraded_error_code is None:
        return

    if isinstance(degraded_error_code, bytes):
        degraded_error_code = degraded_error_code.decode("utf-8", errors="ignore")

    raise CvExtractionProviderUnavailableError(
        "CV extraction is temporarily unavailable while the provider recovers. "
        "Please retry shortly."
    )


async def record_cv_extraction_provider_failure(
    *,
    arq_redis: ArqRedis,
    error_code: str,
) -> None:
    """Track repeated provider failures and open a short degraded window when needed."""
    if error_code not in _DEGRADATION_ERROR_CODES:
        return

    settings = get_settings()
    failure_count = await arq_redis.incr(_FAILURE_COUNT_KEY)
    if failure_count == 1:
        await arq_redis.expire(
            _FAILURE_COUNT_KEY,
            settings.cv_extraction_provider_failure_window_seconds,
        )

    if failure_count < settings.cv_extraction_provider_failure_threshold:
        return

    await arq_redis.set(
        _DEGRADED_KEY,
        error_code,
        ex=settings.cv_extraction_provider_cooldown_seconds,
    )
    logger.warning(
        "cv_extraction_provider_degraded",
        error_code=error_code,
        failure_count=failure_count,
    )


async def clear_cv_extraction_provider_failures(*, arq_redis: ArqRedis) -> None:
    """Clear short-lived degradation state after a successful extraction."""
    await arq_redis.delete(_FAILURE_COUNT_KEY, _DEGRADED_KEY)
