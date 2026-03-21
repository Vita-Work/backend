from __future__ import annotations

import asyncio

from arq import create_pool
from arq.connections import ArqRedis
from fastapi import Request

from src.extensions.arq.arq_common import REDIS_SETTINGS


async def get_arq_redis(request: Request) -> ArqRedis:
    """Return a shared ARQ Redis pool for the current FastAPI app."""
    redis = getattr(request.app.state, "arq_redis", None)
    if redis is not None:
        return redis

    lock = getattr(request.app.state, "_arq_redis_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        request.app.state._arq_redis_lock = lock

    async with lock:
        redis = getattr(request.app.state, "arq_redis", None)
        if redis is None:
            redis = await create_pool(REDIS_SETTINGS)
            request.app.state.arq_redis = redis

    return redis
