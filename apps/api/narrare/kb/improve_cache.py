"""KB improve result cache — Redis-backed with 10min TTL.

Caches KBImproveAnalysisResponse per entry_id so that:
- Repeated analyze() calls reuse cached results
- apply() can read cached analysis without re-running the LLM
- Cache is invalidated on successful apply()

Usage:
    cache = KBImproveCache(RedisSessionCache(settings.redis_url))
    await cache.set(entry_id, result.model_dump_json())
    data = await cache.get(entry_id)       # str | None
    await cache.delete(entry_id)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.writing.session_manager import SessionCacheProtocol

logger = structlog.get_logger(__name__)

IMPROVE_TTL = 600  # 10 minutes
IMPROVE_KEY_PREFIX = "kb:improve:"


class KBImproveCache:
    """Redis-backed cache for KB improve analysis results.

    Args:
        cache: Injected cache backend (Redis in production).
    """

    def __init__(self, cache: SessionCacheProtocol) -> None:
        self._cache = cache

    def _key(self, entry_id: str) -> str:
        return f"{IMPROVE_KEY_PREFIX}{entry_id}"

    async def get(self, entry_id: str) -> str | None:
        """Get cached analysis for an entry.

        Args:
            entry_id: The KB entry UUID as a string.

        Returns:
            The cached JSON string, or ``None`` if not found or unreachable.
        """
        key = self._key(entry_id)
        try:
            data = await self._cache.get(key)
        except Exception:
            logger.warning("kb_improve_cache_unavailable", entry_id=entry_id)
            return None
        if data is not None:
            logger.debug("kb_improve_cache_hit", entry_id=entry_id)
        return data

    async def set(self, entry_id: str, value: str) -> None:
        """Cache analysis result with 10min TTL.

        Args:
            entry_id: The KB entry UUID as a string.
            value: The JSON-serialised analysis response.
        """
        key = self._key(entry_id)
        await self._cache.set(key, value, ttl_seconds=IMPROVE_TTL)
        logger.debug("kb_improve_cache_set", entry_id=entry_id)

    async def delete(self, entry_id: str) -> None:
        """Invalidate cached analysis.

        Succeeds silently even when the key does not exist.

        Args:
            entry_id: The KB entry UUID as a string.
        """
        key = self._key(entry_id)
        await self._cache.delete(key)
        logger.debug("kb_improve_cache_invalidated", entry_id=entry_id)
