"""Unit tests for ``WorldbuildingCache`` — Redis-backed worldbuilding cache.

Mirrors ``test_kb_improve_cache.py``: key formatting, entity-type hashing,
get/set/delete delegation, graceful degradation when the backend is
unreachable, and the ``delete_all`` unfiltered-key invalidation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from narrare.kb.worldbuilding_cache import WorldbuildingCache
from narrare_core.writing.session_manager import SessionCacheProtocol


def _make_cache() -> tuple[WorldbuildingCache, AsyncMock]:
    """Build a WorldbuildingCache backed by a mocked SessionCacheProtocol."""
    backend = AsyncMock(spec=SessionCacheProtocol)
    return WorldbuildingCache(cache=backend), backend


# ---------------------------------------------------------------------------
# Entity-type hashing
# ---------------------------------------------------------------------------


class TestHashEntityTypes:
    def test_none_returns_empty(self) -> None:
        assert WorldbuildingCache.hash_entity_types(None) == ""

    def test_empty_list_returns_empty(self) -> None:
        assert WorldbuildingCache.hash_entity_types([]) == ""

    def test_order_independent(self) -> None:
        """Sorting makes the hash stable across input ordering."""
        a = WorldbuildingCache.hash_entity_types(["character", "location"])
        b = WorldbuildingCache.hash_entity_types(["location", "character"])
        assert a == b
        assert a.startswith(":")
        assert len(a) == 9  # ":" + 8 hex chars


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


class TestWorldbuildingCacheGet:
    async def test_returns_cached_string(self) -> None:
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value='{"analysis": "x"}')

        result = await cache.get("novel-1")

        assert result == '{"analysis": "x"}'
        backend.get.assert_awaited_once_with("kb:worldbuild:novel-1")

    async def test_missing_key_returns_none(self) -> None:
        cache, backend = _make_cache()
        backend.get = AsyncMock(return_value=None)

        assert await cache.get("novel-1") is None

    async def test_unavailable_backend_returns_none(self) -> None:
        """A backend exception degrades to None instead of propagating."""
        cache, backend = _make_cache()
        backend.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        assert await cache.get("novel-1") is None


# ---------------------------------------------------------------------------
# Set / Delete / Delete-all
# ---------------------------------------------------------------------------


class TestWorldbuildingCacheSet:
    async def test_stores_with_ttl(self) -> None:
        cache, backend = _make_cache()
        backend.set = AsyncMock()

        await cache.set("novel-1", '{"analysis": "x"}')

        backend.set.assert_awaited_once_with(
            "kb:worldbuild:novel-1", '{"analysis": "x"}', ttl_seconds=600
        )

    async def test_stores_with_entity_types_hash(self) -> None:
        cache, backend = _make_cache()
        backend.set = AsyncMock()

        await cache.set("novel-1", "{}", ":abcd1234")

        backend.set.assert_awaited_once_with(
            "kb:worldbuild:novel-1:abcd1234", "{}", ttl_seconds=600
        )


class TestWorldbuildingCacheDelete:
    async def test_delete_removes_specific_variant(self) -> None:
        cache, backend = _make_cache()
        backend.delete = AsyncMock()

        await cache.delete("novel-1", ":abcd1234")

        backend.delete.assert_awaited_once_with("kb:worldbuild:novel-1:abcd1234")

    async def test_delete_all_removes_unfiltered_key(self) -> None:
        cache, backend = _make_cache()
        backend.delete = AsyncMock()

        await cache.delete_all("novel-1")

        backend.delete.assert_awaited_once_with("kb:worldbuild:novel-1")
