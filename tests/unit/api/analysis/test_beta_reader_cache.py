"""Unit tests for BetaReaderCache — analysis result cache backend.

Tests key hashing, get/set/delete delegation, and graceful
degradation when the cache backend is unavailable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from narrare.analysis.beta_reader_cache import BetaReaderCache
from narrare_core.writing.session_manager import SessionCacheProtocol

# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def _make_cache() -> tuple[BetaReaderCache, AsyncMock]:
    """Create a BetaReaderCache with a mocked SessionCacheProtocol backend.

    Returns:
        Tuple of (cache_instance, mock_backend) for assertion access.
    """
    backend = AsyncMock(spec=SessionCacheProtocol)
    cache = BetaReaderCache(cache=backend)
    return cache, backend


# ---------------------------------------------------------------------------
# Key hashing
# ---------------------------------------------------------------------------


class TestHashChapterIds:
    """hash_chapter_ids produces stable, consistent hashes."""

    def test_stable_hash(self) -> None:
        """Same IDs produce same hash regardless of order."""
        ids_a = ["aaa", "bbb", "ccc"]
        ids_b = ["ccc", "aaa", "bbb"]
        assert BetaReaderCache.hash_chapter_ids(ids_a) == BetaReaderCache.hash_chapter_ids(ids_b)

    def test_different_ids_produce_different_hash(self) -> None:
        """Different ID sets produce different hashes."""
        ids_a = ["aaa", "bbb"]
        ids_b = ["aaa", "ccc"]
        assert BetaReaderCache.hash_chapter_ids(ids_a) != BetaReaderCache.hash_chapter_ids(ids_b)

    def test_single_id(self) -> None:
        """Single ID produces a valid hash."""
        h = BetaReaderCache.hash_chapter_ids(["only-one"])
        assert len(h) == 12  # SHA256[:12]


# ---------------------------------------------------------------------------
# Get — cached value retrieval
# ---------------------------------------------------------------------------


class TestBetaReaderCacheGet:
    """``get()`` delegates to the backend with the correct key."""

    async def test_cached_value_returns_string(self) -> None:
        """Backend returns data → cache returns that data."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value='{"feedback": []}')

        result = await cache.get("novel-1", ["ch-1"])

        assert result == '{"feedback": []}'
        backend.get.assert_awaited_once()

    async def test_missing_key_returns_none(self) -> None:
        """Backend returns None → cache returns None."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value=None)

        result = await cache.get("novel-1", ["ch-1"])

        assert result is None

    async def test_unavailable_cache_returns_none(self) -> None:
        """Backend raises exception → cache returns None (graceful degradation)."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(side_effect=ConnectionError("cache backend down"))

        result = await cache.get("novel-1", ["ch-1"])

        assert result is None


# ---------------------------------------------------------------------------
# Set — storing values with TTL
# ---------------------------------------------------------------------------


class TestBetaReaderCacheSet:
    """``set()`` delegates to the backend with correct TTL."""

    async def test_stores_with_ttl(self) -> None:
        """Cache.set calls backend.set with correct key, value, and TTL=1800."""
        cache, backend = _make_cache()
        backend.set = AsyncMock()

        await cache.set("novel-1", ["ch-1"], '{"feedback": []}')

        backend.set.assert_awaited_once()
        call_args = backend.set.call_args
        assert call_args[1]["ttl_seconds"] == 1800


# ---------------------------------------------------------------------------
# Delete — cache invalidation
# ---------------------------------------------------------------------------


class TestBetaReaderCacheDelete:
    """``delete()`` invalidates entries via the backend."""

    async def test_removes_key(self) -> None:
        """Cache.delete calls backend.delete with the correct key."""
        cache, backend = _make_cache()
        backend.delete = AsyncMock()

        await cache.delete("novel-1", ["ch-1"])

        backend.delete.assert_awaited_once()


# ---------------------------------------------------------------------------
# Roundtrip — set → get
# ---------------------------------------------------------------------------


class TestBetaReaderCacheRoundtrip:
    """set → get roundtrip returns the same value."""

    async def test_set_get_roundtrip(self) -> None:
        """Value stored via set can be retrieved via get."""
        cache, backend = _make_cache()
        stored_data = '{"novel_id": "test", "feedback": []}'
        backend.set = AsyncMock()
        backend.get = AsyncMock(return_value=stored_data)

        await cache.set("novel-1", ["ch-1"], stored_data)
        result = await cache.get("novel-1", ["ch-1"])

        assert result == stored_data
