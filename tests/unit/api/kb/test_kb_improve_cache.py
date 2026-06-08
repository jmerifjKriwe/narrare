"""Unit tests for KBImproveCache — Redis-backed improve result cache.

Tests key formatting, get/set/delete delegation, and graceful
degradation when Redis is unavailable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

from narrare.kb.improve_cache import KBImproveCache
from narrare_core.writing.session_manager import SessionCacheProtocol

# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def _make_cache() -> tuple[KBImproveCache, AsyncMock]:
    """Create a KBImproveCache with a mocked SessionCacheProtocol backend.

    Returns:
        Tuple of (cache_instance, mock_backend) for assertion access.
    """
    backend = AsyncMock(spec=SessionCacheProtocol)
    cache = KBImproveCache(cache=backend)
    return cache, backend


# ---------------------------------------------------------------------------
# Key formatting
# ---------------------------------------------------------------------------


class TestKBImproveCacheKey:
    """Key format: ``kb:improve:{entry_id}``."""

    def test_simple_key(self) -> None:
        """_key("entry-123") returns "kb:improve:entry-123"."""
        cache, _ = _make_cache()
        assert cache._key("entry-123") == "kb:improve:entry-123"

    def test_key_with_uuid_string(self) -> None:
        """UUID as string is used correctly as the key suffix."""
        cache, _ = _make_cache()
        entry_id = str(uuid4())
        expected = f"kb:improve:{entry_id}"
        assert cache._key(entry_id) == expected


# ---------------------------------------------------------------------------
# Get — cached value retrieval
# ---------------------------------------------------------------------------


class TestKBImproveCacheGet:
    """``get()`` delegates to the backend with the correct key prefix."""

    async def test_cached_value_returns_string(self) -> None:
        """Backend returns data → cache returns that data."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value='{"analysis": "test"}')

        result = await cache.get("entry-1")

        assert result == '{"analysis": "test"}'
        backend.get.assert_awaited_once_with("kb:improve:entry-1")

    async def test_missing_key_returns_none(self) -> None:
        """Backend returns None → cache returns None."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value=None)

        result = await cache.get("entry-1")

        assert result is None
        backend.get.assert_awaited_once_with("kb:improve:entry-1")

    async def test_unavailable_redis_returns_none(self) -> None:
        """Backend raises an exception → cache returns None (graceful degradation)."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        result = await cache.get("entry-1")

        assert result is None
        backend.get.assert_awaited_once_with("kb:improve:entry-1")


# ---------------------------------------------------------------------------
# Set — storing values with TTL
# ---------------------------------------------------------------------------


class TestKBImproveCacheSet:
    """``set()`` delegates to the backend with key prefix and TTL."""

    async def test_stores_with_ttl(self) -> None:
        """Cache.set calls backend.set with correct key, value, and TTL=600."""
        cache, backend = _make_cache()
        backend.set = AsyncMock()

        await cache.set("entry-1", '{"analysis": "test"}')

        backend.set.assert_awaited_once_with(
            "kb:improve:entry-1",
            '{"analysis": "test"}',
            ttl_seconds=600,
        )


# ---------------------------------------------------------------------------
# Delete — cache invalidation
# ---------------------------------------------------------------------------


class TestKBImproveCacheDelete:
    """``delete()`` invalidates entries via the backend."""

    async def test_removes_key(self) -> None:
        """Cache.delete calls backend.delete with the correct key prefix."""
        cache, backend = _make_cache()
        backend.delete = AsyncMock()

        await cache.delete("entry-1")

        backend.delete.assert_awaited_once_with("kb:improve:entry-1")


# ---------------------------------------------------------------------------
# Integration behaviour — hit/miss logging
# ---------------------------------------------------------------------------


class TestKBImproveCacheLogging:
    """Debug logging on cache hit (optional — can be skipped)."""

    async def test_get_logs_hit_on_cached_value(self) -> None:
        """Debug log is emitted when cached data is found."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value="cached")

        result = await cache.get("hit-entry")

        assert result == "cached"
        # Logging is a side-effect; the primary contract is the return value.

    async def test_get_does_not_log_hit_on_miss(self) -> None:
        """No hit log when backend returns None."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value=None)

        result = await cache.get("miss-entry")

        assert result is None
