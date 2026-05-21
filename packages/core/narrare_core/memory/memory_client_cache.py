"""LRU cache for mem0 AsyncMemory instances per user."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MemoryClientCache:
    """Bounded LRU cache for mem0 AsyncMemory instances.

    Clients are created on first access and reused until settings change.
    """

    def __init__(self, max_size: int = 100) -> None:
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._max_size = max_size

    def get(self, user_id: str) -> Any | None:
        """Retrieve a cached client, moving it to the end (most recently used)."""
        if user_id in self._cache:
            self._cache.move_to_end(user_id)
            return self._cache[user_id]
        return None

    def put(self, user_id: str, client: Any) -> None:
        """Cache a client, evicting the oldest entry if over capacity."""
        if user_id in self._cache:
            self._cache.move_to_end(user_id)
        self._cache[user_id] = client
        if len(self._cache) > self._max_size:
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug("memory_cache_evicted", user_id=evicted_key)

    def invalidate(self, user_id: str) -> None:
        """Remove a cached client (e.g. when settings change)."""
        self._cache.pop(user_id, None)

    def clear(self) -> None:
        """Remove all cached clients."""
        self._cache.clear()
