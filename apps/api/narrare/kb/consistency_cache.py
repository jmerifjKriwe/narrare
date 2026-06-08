"""Redis-backed cache for consistency check results.

Follows the same pattern as worldbuilding_cache.py but with a different
key prefix and project-level caching.

Cache key format: kb:consistency:{novel_id}{entity_types_hash}
TTL: 10 minutes (600s)

Usage:
    cache = ConsistencyCache(RedisSessionCache(settings.redis_url))
    await cache.set(novel_id, result.model_dump_json())
    data = await cache.get(novel_id)             # str | None
    await cache.delete_all(novel_id)             # Invalidate all variants
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.writing.session_manager import SessionCacheProtocol

logger = structlog.get_logger(__name__)


class ConsistencyCache:
    """Redis-backed cache for consistency check results.

    Args:
        cache: Injected cache backend via SessionCacheProtocol.
        ttl: Cache TTL in seconds.
        key_prefix: Redis key prefix for namespace isolation.
    """

    def __init__(
        self,
        cache: SessionCacheProtocol,
        *,
        ttl: int = 600,
        key_prefix: str = "kb:consistency:",
    ) -> None:
        self._cache = cache
        self._ttl = ttl
        self._key_prefix = key_prefix

    def _key(self, novel_id: str, entity_types_hash: str = "") -> str:
        return f"{self._key_prefix}{novel_id}{entity_types_hash}"

    @staticmethod
    def hash_entity_types(entity_types: list[str] | None) -> str:
        """Create a stable hash suffix for entity type filtering.

        Args:
            entity_types: List of entity type strings, or None (all types).

        Returns:
            Empty string if None, otherwise ``f":{md5_8char}"``.
        """
        if not entity_types:
            return ""
        import hashlib

        raw = ",".join(sorted(entity_types))
        h = hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:8]
        return f":{h}"

    async def get(self, novel_id: str, entity_types_hash: str = "") -> str | None:
        """Get cached consistency check result for a project.

        Args:
            novel_id: The project ID (UUID as string).
            entity_types_hash: Optional entity type filter hash
                from :meth:`hash_entity_types`.

        Returns:
            The cached JSON string, or ``None`` if not found or unreachable.
        """
        key = self._key(novel_id, entity_types_hash)
        try:
            data = await self._cache.get(key)
        except Exception:
            logger.warning(
                "consistency_cache_unavailable",
                novel_id=novel_id,
            )
            return None
        if data is not None:
            logger.debug(
                "consistency_cache_hit",
                novel_id=novel_id,
                entity_types_hash=entity_types_hash or None,
            )
        return data

    async def set(
        self,
        novel_id: str,
        value: str,
        entity_types_hash: str = "",
    ) -> None:
        """Cache consistency check result with 10-minute TTL.

        Args:
            novel_id: The project ID (UUID as string).
            value: JSON-serialised consistency check response.
            entity_types_hash: Optional entity type filter hash
                from :meth:`hash_entity_types`.
        """
        key = self._key(novel_id, entity_types_hash)
        await self._cache.set(key, value, ttl_seconds=self._ttl)
        logger.debug(
            "consistency_cache_set",
            novel_id=novel_id,
            entity_types_hash=entity_types_hash or None,
        )

    async def delete(self, novel_id: str, entity_types_hash: str = "") -> None:
        """Invalidate a specific cached consistency check variant.

        Succeeds silently even when the key does not exist.

        Args:
            novel_id: The project ID (UUID as string).
            entity_types_hash: Optional entity type filter hash.
        """
        key = self._key(novel_id, entity_types_hash)
        await self._cache.delete(key)
        logger.debug(
            "consistency_cache_invalidated",
            novel_id=novel_id,
            entity_types_hash=entity_types_hash or None,
        )

    async def delete_all(self, novel_id: str) -> None:
        """Invalidate all cached consistency checks for a project.

        Removes the unfiltered key (``kb:consistency:{novel_id}``).
        Filtered variants (with entity type hashes) are not removed
        by this call — they expire naturally via TTL.

        Args:
            novel_id: The project ID (UUID as string).
        """
        key = self._key(novel_id)
        await self._cache.delete(key)
        logger.debug(
            "consistency_cache_delete_all",
            novel_id=novel_id,
        )
