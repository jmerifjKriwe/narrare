"""Beta reader analysis result cache — Redis-backed with 30min TTL.

Caches BetaReaderResponse per novel+chapters so that:
- Repeated analyze() calls reuse cached results
- deep_dive() can read Phase 1 from cache without re-running the LLM
- Cache key includes chapter IDs for natural invalidation

Usage:
    cache = BetaReaderCache(RedisSessionCache(settings.redis_url))
    await cache.set(novel_id, chapter_ids, result.model_dump_json())
    data = await cache.get(novel_id, chapter_ids)  # str | None
    await cache.delete(novel_id, chapter_ids)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.writing.session_manager import SessionCacheProtocol

logger = structlog.get_logger(__name__)

BETA_READER_TTL = 1800  # 30 minutes
BETA_READER_KEY_PREFIX = "analysis:beta:"


class BetaReaderCache:
    """Redis-backed cache for beta reader analysis results.

    Args:
        cache: Injected cache backend (Redis in production).
    """

    def __init__(self, cache: SessionCacheProtocol) -> None:
        self._cache = cache

    def _key(self, novel_id: str, chapter_ids_hash: str) -> str:
        """Build cache key from novel ID and chapter IDs hash.

        Args:
            novel_id: Novel UUID as string.
            chapter_ids_hash: Stable hash of sorted chapter IDs.

        Returns:
            Cache key string.
        """
        return f"{BETA_READER_KEY_PREFIX}{novel_id}:{chapter_ids_hash}"

    @staticmethod
    def hash_chapter_ids(chapter_ids: list[str]) -> str:
        """Create stable hash from sorted chapter IDs.

        Args:
            chapter_ids: List of chapter UUID strings.

        Returns:
            12-character hex hash string.
        """
        import hashlib

        sorted_ids = ",".join(sorted(chapter_ids))
        return hashlib.sha256(sorted_ids.encode()).hexdigest()[:12]

    async def get(self, novel_id: str, chapter_ids: list[str]) -> str | None:
        """Get cached analysis for a set of chapters.

        Args:
            novel_id: The novel UUID as a string.
            chapter_ids: The chapter IDs that were analyzed.

        Returns:
            The cached JSON string, or ``None`` if not found or unreachable.
        """
        key = self._key(novel_id, self.hash_chapter_ids(chapter_ids))
        try:
            data = await self._cache.get(key)
        except Exception:
            logger.warning("beta_reader_cache_unavailable", novel_id=novel_id)
            return None
        if data is not None:
            logger.debug("beta_reader_cache_hit", novel_id=novel_id)
        return data

    async def set(self, novel_id: str, chapter_ids: list[str], value: str) -> None:
        """Cache analysis result with 30min TTL.

        Args:
            novel_id: The novel UUID as a string.
            chapter_ids: The chapter IDs that were analyzed.
            value: The JSON-serialised analysis response.
        """
        key = self._key(novel_id, self.hash_chapter_ids(chapter_ids))
        await self._cache.set(key, value, ttl_seconds=BETA_READER_TTL)
        logger.debug("beta_reader_cache_set", novel_id=novel_id)

    async def delete(self, novel_id: str, chapter_ids: list[str]) -> None:
        """Invalidate cached analysis.

        Succeeds silently even when the key does not exist.

        Args:
            novel_id: The novel UUID as a string.
            chapter_ids: The chapter IDs that were analyzed.
        """
        key = self._key(novel_id, self.hash_chapter_ids(chapter_ids))
        await self._cache.delete(key)
        logger.debug("beta_reader_cache_invalidated", novel_id=novel_id)
