"""No-op memory client for graceful degradation when mem0 is unavailable.

Every method logs a warning and returns empty results so callers never
need to handle ``None`` or missing client state.

Method signatures match the mem0 2.0.x ``AsyncMemory`` API so callers
can rely on explicit, typed parameters instead of opaque ``**kwargs``.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class NullMemoryClient:
    """No-op memory client used when mem0 is unavailable.

    Every method logs a warning and returns empty results so callers
    never need to handle ``None`` or missing client state.

    Method signatures match the mem0 2.0.x ``AsyncMemory`` API so
    callers can rely on explicit, typed parameters instead of opaque
    ``**kwargs``.
    """

    async def add(
        self,
        *,
        messages: str | list[dict[str, str]],
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, list[Any]]:
        """No-op add — logs warning and returns empty results."""
        logger.warning("mem0_unavailable", method="add")
        return {"results": [], "relations": []}

    async def search(
        self,
        *,
        query: str,
        top_k: int = 20,
        filters: dict[str, Any] | None = None,
        threshold: float = 0.1,
        **kwargs: Any,
    ) -> dict[str, list[Any]]:
        """No-op search — logs warning and returns empty results."""
        logger.warning("mem0_unavailable", method="search")
        return {"results": []}

    async def get_all(
        self,
        *,
        filters: dict[str, Any] | None = None,
        top_k: int = 20,
        **kwargs: Any,
    ) -> dict[str, list[Any]]:
        """No-op get_all — logs warning and returns empty results."""
        logger.warning("mem0_unavailable", method="get_all")
        return {"results": []}

    async def delete(
        self,
        *,
        memory_id: str,
        **kwargs: Any,
    ) -> dict[str, list[Any]]:
        """No-op delete — logs warning and returns empty results."""
        logger.warning("mem0_unavailable", method="delete")
        return {"results": []}

    async def delete_all(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, list[Any]]:
        """No-op delete_all — logs warning and returns empty results."""
        logger.warning("mem0_unavailable", method="delete_all")
        return {"results": []}
