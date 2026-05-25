"""Redis-backed session cache implementing SessionCacheProtocol.

Gracefully degrades when Redis is unavailable — returns ``None`` on cache
misses, logs warnings on connectivity errors.  Never blocks the request
with an unhandled exception.

Uses lazy import of ``redis.asyncio`` (only inside ``_get_client()``) so
this module can be safely imported even when the ``redis`` package is not
installed.  This is the only place in ``core/`` that imports Redis
(RULE-08).

See:
    :class:`narrare_core.writing.session_manager.SessionCacheProtocol`
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RedisSessionCache:
    """Redis-backed session cache.

    Implements :class:`SessionCacheProtocol` from
    ``core/writing/session_manager.py``.

    Uses lazy client initialisation — the Redis connection is created on
    the first call to :meth:`get`, :meth:`set`, or :meth:`delete`.  All
    three methods degrade gracefully: connectivity failures are logged
    but never propagated to the caller.

    Args:
        redis_url:
            Redis connection URL (e.g. ``"redis://localhost:6379/0"``).
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: Any = None

    # ------------------------------------------------------------------
    # Public API — SessionCacheProtocol
    # ------------------------------------------------------------------

    async def get(self, key: str) -> str | None:
        """Get a cached value.

        Returns the value as a string, or ``None`` when the key does not
        exist or when Redis is unreachable.
        """
        try:
            client = await self._get_client()
            return await client.get(key)
        except Exception:
            logger.warning("redis_cache_get_failed", key=key, exc_info=True)
            return None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Set a cached value with an optional TTL.

        When *ttl_seconds* is ``None`` the key persists indefinitely
        (subject to Redis eviction policy).  Failures are logged but
        never propagated.
        """
        try:
            client = await self._get_client()
            if ttl_seconds is not None:
                await client.setex(key, ttl_seconds, value)
            else:
                await client.set(key, value)
        except Exception:
            logger.warning("redis_cache_set_failed", key=key, exc_info=True)

    async def delete(self, key: str) -> None:
        """Delete a cached value.

        Succeeds silently even when *key* does not exist.  Failures are
        logged but never propagated.
        """
        try:
            client = await self._get_client()
            await client.delete(key)
        except Exception:
            logger.warning("redis_cache_delete_failed", key=key, exc_info=True)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _get_client(self) -> Any:
        """Return the lazy-initialised Redis client.

        The actual ``redis.asyncio`` import is deferred until this
        method is called, allowing the module to be imported in
        environments where the ``redis`` package is not installed.
        """
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
        return self._redis
