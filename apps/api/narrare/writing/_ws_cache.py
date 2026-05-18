"""In-memory session cache for WebSocket interactive sessions.

This is a simple dict-backed implementation of SessionCacheProtocol.
For production, use the Redis-backed implementation from the cache module.
"""

from __future__ import annotations


class InMemorySessionCache:
    """Simple in-memory dict implementing SessionCacheProtocol.

    Suitable for development and testing.  For production use the
    Redis-backed implementation from ``narrare.cache``.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        """Get a cached value."""
        return self._store.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set a cached value (TTL ignored in-memory)."""
        self._store[key] = value

    async def delete(self, key: str) -> None:
        """Delete a cached value."""
        self._store.pop(key, None)
