from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import OperationalError

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


async def invoke_search_setup_graph(
    *,
    graph_input,
    config: dict[str, object],
    durability: str = "sync",
):
    """Invoke the shared graph and self-heal the runtime once on stale checkpointer errors."""
    graph = await get_search_setup_graph()
    try:
        return await graph.ainvoke(graph_input, config, durability=durability)
    except OperationalError as exc:
        if not _is_stale_runtime_error(exc):
            raise
        logger.warning("search_setup_runtime_retrying_invoke", error=str(exc))
        await force_restart_search_setup_runtime()
        graph = await get_search_setup_graph()
        return await graph.ainvoke(graph_input, config, durability=durability)


async def get_search_setup_state(config: dict[str, object]):
    """Fetch graph state and self-heal the runtime once on stale checkpointer errors."""
    graph = await get_search_setup_graph()
    try:
        return await graph.aget_state(config)
    except OperationalError as exc:
        if not _is_stale_runtime_error(exc):
            raise
        logger.warning("search_setup_runtime_retrying_state_read", error=str(exc))
        await force_restart_search_setup_runtime()
        graph = await get_search_setup_graph()
        return await graph.aget_state(config)


async def start_search_setup_runtime() -> None:
    """Initialize the persistent LangGraph runtime once per process."""
    global _checkpointer_cm, _checkpointer, _graph

    if _runtime_is_healthy():
        return

    async with _runtime_lock:
        if _runtime_is_healthy():
            return

        if _checkpointer_cm is not None:
            await _close_runtime()
            logger.warning(
                "search_setup_runtime_restarting",
                reason="stale_checkpointer_connection",
            )

        _checkpointer_cm = AsyncPostgresSaver.from_conn_string(get_sync_database_url())
        _checkpointer = await _checkpointer_cm.__aenter__()
        await _checkpointer.setup()
        _graph = build_search_setup_graph(checkpointer=_checkpointer)
        logger.info("search_setup_runtime_started")


async def stop_search_setup_runtime() -> None:
    """Close the shared search-setup runtime."""
    async with _runtime_lock:
        await _close_runtime()
        logger.info("search_setup_runtime_stopped")


async def force_restart_search_setup_runtime() -> None:
    """Force-close and recreate the shared search-setup runtime."""
    async with _runtime_lock:
        await _close_runtime()
    await start_search_setup_runtime()


def _runtime_is_healthy() -> bool:
    if _graph is None or _checkpointer is None:
        return False
    connection = getattr(_checkpointer, "conn", None)
    if connection is None:
        return False
    return not bool(getattr(connection, "closed", True))


async def _close_runtime() -> None:
    global _checkpointer_cm, _checkpointer, _graph

    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)
    _checkpointer_cm = None
    _checkpointer = None
    _graph = None


def _is_stale_runtime_error(exc: OperationalError) -> bool:
    return "connection is closed" in str(exc).lower()
