from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.db.url import get_sync_database_url
from src.logger import get_logger
from src.workflows.search_setup.graph import build_search_setup_graph

logger = get_logger("workflows.search_setup.runtime")

_runtime_lock = asyncio.Lock()
_checkpointer_cm: AbstractAsyncContextManager[AsyncPostgresSaver] | None = None
_checkpointer: AsyncPostgresSaver | None = None
_graph = None


async def get_search_setup_graph() -> object:
    """Return the shared search-setup graph, initializing the runtime if needed."""
    await start_search_setup_runtime()
    return _graph


async def start_search_setup_runtime() -> None:
    """Initialize the persistent LangGraph runtime once per process."""
    global _checkpointer_cm, _checkpointer, _graph

    if _graph is not None:
        return

    async with _runtime_lock:
        if _graph is not None:
            return

        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(get_sync_database_url())
        _checkpointer = await _checkpointer_cm.__aenter__()
        await _checkpointer.setup()
        _graph = build_search_setup_graph(checkpointer=_checkpointer)
        logger.info("search_setup_runtime_started")


async def stop_search_setup_runtime() -> None:
    """Close the shared search-setup runtime."""
    global _checkpointer_cm, _checkpointer, _graph

    async with _runtime_lock:
        if _checkpointer_cm is not None:
            await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer_cm = None
        _checkpointer = None
        _graph = None
        logger.info("search_setup_runtime_stopped")
