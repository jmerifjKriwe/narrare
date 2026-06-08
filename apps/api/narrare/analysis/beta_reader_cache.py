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


class BetaReaderCache:
    """Redis-backed cache for beta reader analysis results.

    Args:
        cache: Injected cache backend (Redis in production).
        ttl: Cache TTL in seconds.
        key_prefix: Redis key prefix for namespace isolation.
    """

    def __init__(
        self,
        cache: SessionCacheProtocol,
        *,
        ttl: int = 1800,
        key_prefix: str = "analysis:beta:",
    ) -> None:
        self._cache = cache
        self._ttl = ttl
        self._key_prefix = key_prefix

    def _key(self, novel_id: str, chapter_ids_hash: str) -> str:
        """Build cache key from novel ID and chapter IDs hash.

        Args:
            novel_id: Novel UUID as string.
            chapter_ids_hash: Stable hash of sorted chapter IDs.

        Returns:
            Cache key string.
        """
        return f"{self._key_prefix}{novel_id}:{chapter_ids_hash}"

    @staticmethod
    def hash_chapter_ids(chapter_ids: list[str], content_hash: str = "") -> str:
        """Create stable hash from sorted chapter IDs and optional content.

        When ``content_hash`` is provided, it is combined with the chapter IDs
        so that edits to chapter text produce a different cache key (ADR-021).

        Args:
            chapter_ids: List of chapter UUID strings.
            content_hash: Optional short hash of the chapter text content.

        Returns:
            12-character hex hash string.
        """
        import hashlib

        sorted_ids = ",".join(sorted(chapter_ids))
        combined = f"{sorted_ids}:{content_hash}" if content_hash else sorted_ids
        return hashlib.sha256(combined.encode()).hexdigest()[:12]

    async def get(
        self,
        novel_id: str,
        chapter_ids: list[str],
        content_hash: str = "",
    ) -> str | None:
        """Get cached analysis for a set of chapters.

        Args:
            novel_id: The novel UUID as a string.
            chapter_ids: The chapter IDs that were analyzed.
            content_hash: Optional content hash for cache-key discrimination.

        Returns:
            The cached JSON string, or ``None`` if not found or unreachable.
        """
        key = self._key(novel_id, self.hash_chapter_ids(chapter_ids, content_hash))
        try:
            data = await self._cache.get(key)
        except Exception:
            logger.warning("beta_reader_cache_unavailable", novel_id=novel_id)
            return None
        if data is not None:
            logger.debug("beta_reader_cache_hit", novel_id=novel_id)
        return data

    async def set(
        self,
        novel_id: str,
        chapter_ids: list[str],
        value: str,
        content_hash: str = "",
    ) -> None:
        """Cache analysis result with 30min TTL.

        Args:
            novel_id: The novel UUID as a string.
            chapter_ids: The chapter IDs that were analyzed.
            value: The JSON-serialised analysis response.
            content_hash: Optional content hash for cache-key discrimination.
        """
        key = self._key(novel_id, self.hash_chapter_ids(chapter_ids, content_hash))
        await self._cache.set(key, value, ttl_seconds=self._ttl)
        logger.debug("beta_reader_cache_set", novel_id=novel_id)

    async def delete(
        self,
        novel_id: str,
        chapter_ids: list[str],
        content_hash: str = "",
    ) -> None:
        """Invalidate cached analysis.

        Succeeds silently even when the key does not exist.

        Args:
            novel_id: The novel UUID as a string.
            chapter_ids: The chapter IDs that were analyzed.
            content_hash: Optional content hash for cache-key discrimination.
        """
        key = self._key(novel_id, self.hash_chapter_ids(chapter_ids, content_hash))
        await self._cache.delete(key)
        logger.debug("beta_reader_cache_invalidated", novel_id=novel_id)
