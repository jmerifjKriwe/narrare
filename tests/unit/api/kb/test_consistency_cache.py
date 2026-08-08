"""Unit tests for ConsistencyCache — consistency check result cache backend.

Tests key formatting, entity type hashing, get/set/delete delegation,
and graceful degradation when the cache backend is unavailable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from narrare.kb.consistency_cache import (
    ConsistencyCache,
)
from narrare_core.writing.session_manager import SessionCacheProtocol

# ---------------------------------------------------------------------------
# Fake dependencies
# ---------------------------------------------------------------------------


class FakeSessionCache:
    """In-memory fake for SessionCacheProtocol.

    Supports get/set/delete with optional TTL tracking.
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        self._data[key] = value
        if ttl_seconds is not None:
            self._ttls[key] = ttl_seconds

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._ttls.pop(key, None)


def _make_cache() -> tuple[ConsistencyCache, AsyncMock]:
    """Create a ConsistencyCache with a mocked backend.

    Returns:
        Tuple of (cache_instance, mock_backend) for assertion access.
    """
    backend = AsyncMock(spec=SessionCacheProtocol)
    cache = ConsistencyCache(cache=backend)
    return cache, backend


# ---------------------------------------------------------------------------
# hash_entity_types — static hash helper
# ---------------------------------------------------------------------------


class TestHashEntityTypes:
    """``hash_entity_types`` produces stable, collision-resistant suffixes."""

    def test_none_returns_empty_string(self) -> None:
        """None input (no filter) returns empty string."""
        assert ConsistencyCache.hash_entity_types(None) == ""

    def test_empty_list_returns_empty_string(self) -> None:
        """Empty list is treated the same as None."""
        assert ConsistencyCache.hash_entity_types([]) == ""

    def test_single_type_returns_hash_suffix(self) -> None:
        """Single entity type returns ':<8-char-hash>'."""
        result = ConsistencyCache.hash_entity_types(["character"])
        assert result.startswith(":")
        # MD5 hex[:8] = 8 characters after ':'
        assert len(result) == 9  # ':' + 8 hex chars

    def test_multiple_types_returns_hash_suffix(self) -> None:
        """Multiple entity types are sorted then hashed."""
        result = ConsistencyCache.hash_entity_types(["location", "character"])
        assert result.startswith(":")
        assert len(result) == 9

    def test_sorted_stability(self) -> None:
        """Order of input does not matter — sorted before hashing."""
        a = ConsistencyCache.hash_entity_types(["character", "location"])
        b = ConsistencyCache.hash_entity_types(["location", "character"])
        assert a == b

    def test_different_types_produce_different_hashes(self) -> None:
        """Different entity type sets produce different hashes."""
        a = ConsistencyCache.hash_entity_types(["character"])
        b = ConsistencyCache.hash_entity_types(["location"])
        assert a != b


# ---------------------------------------------------------------------------
# Key formatting
# ---------------------------------------------------------------------------


class TestConsistencyCacheKey:
    """Key format: ``kb:consistency:{novel_id}{entity_types_hash}``."""

    def test_key_without_hash(self) -> None:
        """_key with no hash suffix produces prefix + novel_id."""
        cache, _ = _make_cache()
        assert cache._key("novel-123") == "kb:consistency:novel-123"

    def test_key_with_hash(self) -> None:
        """_key includes entity type hash when provided."""
        cache, _ = _make_cache()
        suffix = ":abc12345"
        assert cache._key("novel-123", suffix) == f"kb:consistency:novel-123{suffix}"


# ---------------------------------------------------------------------------
# Get — cached value retrieval
# ---------------------------------------------------------------------------


class TestConsistencyCacheGet:
    """``get()`` returns cached data or None on miss/failure."""

    @pytest.mark.asyncio
    async def test_cached_value_returns_string(self) -> None:
        """Backend returns data → cache returns that data."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value='{"inconsistencies": []}')

        result = await cache.get("novel-1")

        assert result == '{"inconsistencies": []}'
        backend.get.assert_awaited_once_with("kb:consistency:novel-1")

    @pytest.mark.asyncio
    async def test_missing_key_returns_none(self) -> None:
        """Backend returns None → cache returns None."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value=None)

        result = await cache.get("novel-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_exception_returns_none(self) -> None:
        """Backend raises exception → cache returns None (graceful degradation)."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(side_effect=ConnectionError("cache backend down"))

        result = await cache.get("novel-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_passes_entity_types_hash_to_key(self) -> None:
        """Entity types hash is appended to the key."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value=None)

        await cache.get("novel-1", entity_types_hash=":abc12345")

        backend.get.assert_awaited_once_with("kb:consistency:novel-1:abc12345")


# ---------------------------------------------------------------------------
# Set — storing values with TTL
# ---------------------------------------------------------------------------


class TestConsistencyCacheSet:
    """``set()`` stores data with correct key and TTL."""

    @pytest.mark.asyncio
    async def test_stores_with_ttl(self) -> None:
        """Cache.set calls backend.set with correct key, value, and TTL."""
        cache, backend = _make_cache()
        backend.set = AsyncMock()

        await cache.set("novel-1", '{"inconsistencies": []}')

        backend.set.assert_awaited_once_with(
            "kb:consistency:novel-1",
            '{"inconsistencies": []}',
            ttl_seconds=600,
        )

    @pytest.mark.asyncio
    async def test_stores_with_entity_types_hash(self) -> None:
        """Cache.set includes entity types hash in the key."""
        cache, backend = _make_cache()
        backend.set = AsyncMock()

        await cache.set("novel-1", '{"data": 1}', entity_types_hash=":abc12345")

        backend.set.assert_awaited_once_with(
            "kb:consistency:novel-1:abc12345",
            '{"data": 1}',
            ttl_seconds=600,
        )


# ---------------------------------------------------------------------------
# Delete — specific variant invalidation
# ---------------------------------------------------------------------------


class TestConsistencyCacheDelete:
    """``delete()`` removes a specific cached variant."""

    @pytest.mark.asyncio
    async def test_delete_calls_backend_delete(self) -> None:
        """Cache.delete calls backend.delete with the correct key."""
        cache, backend = _make_cache()
        backend.delete = AsyncMock()

        await cache.delete("novel-1")

        backend.delete.assert_awaited_once_with("kb:consistency:novel-1")

    @pytest.mark.asyncio
    async def test_delete_with_entity_types_hash(self) -> None:
        """Cache.delete includes entity types hash in the key."""
        cache, backend = _make_cache()
        backend.delete = AsyncMock()

        await cache.delete("novel-1", entity_types_hash=":abc12345")

        backend.delete.assert_awaited_once_with("kb:consistency:novel-1:abc12345")


# ---------------------------------------------------------------------------
# Delete all — base key invalidation
# ---------------------------------------------------------------------------


class TestConsistencyCacheDeleteAll:
    """``delete_all()`` removes the unfiltered key for a project."""

    @pytest.mark.asyncio
    async def test_delete_all_calls_backend_delete(self) -> None:
        """Cache.delete_all calls backend.delete with the base key (no hash)."""
        cache, backend = _make_cache()
        backend.delete = AsyncMock()

        await cache.delete_all("novel-1")

        backend.delete.assert_awaited_once_with("kb:consistency:novel-1")


# ---------------------------------------------------------------------------
# Integration — fake backend round-trip
# ---------------------------------------------------------------------------


class TestConsistencyCacheRoundTrip:
    """Round-trip tests using the in-memory FakeSessionCache."""

    @pytest.mark.asyncio
    async def test_set_then_get_returns_value(self) -> None:
        """Set followed by get returns the stored value."""
        fake = FakeSessionCache()
        cache = ConsistencyCache(cache=fake)

        await cache.set("novel-1", '{"result": true}')
        result = await cache.get("novel-1")

        assert result == '{"result": true}'

    @pytest.mark.asyncio
    async def test_delete_then_get_returns_none(self) -> None:
        """Delete followed by get returns None."""
        fake = FakeSessionCache()
        cache = ConsistencyCache(cache=fake)

        await cache.set("novel-1", '{"result": true}')
        await cache.delete("novel-1")
        result = await cache.get("novel-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_all_then_get_returns_none(self) -> None:
        """Delete_all removes the base key, subsequent get returns None."""
        fake = FakeSessionCache()
        cache = ConsistencyCache(cache=fake)

        await cache.set("novel-1", '{"result": true}')
        await cache.delete_all("novel-1")
        result = await cache.get("novel-1")

        assert result is None
