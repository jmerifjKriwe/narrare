"""Unit tests for InMemorySessionCache — dict-backed cache implementation."""

from __future__ import annotations

from narrare.writing._ws_cache import InMemorySessionCache


class TestInMemorySessionCache:
    async def test_get_returns_none_for_missing_key(self) -> None:
        cache = InMemorySessionCache()
        assert await cache.get("missing") is None

    async def test_set_and_get_roundtrip(self) -> None:
        cache = InMemorySessionCache()
        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

    async def test_set_overwrites_existing(self) -> None:
        cache = InMemorySessionCache()
        await cache.set("key1", "old")
        await cache.set("key1", "new")
        assert await cache.get("key1") == "new"

    async def test_delete_removes_key(self) -> None:
        cache = InMemorySessionCache()
        await cache.set("key1", "value1")
        await cache.delete("key1")
        assert await cache.get("key1") is None

    async def test_delete_nonexistent_key_no_error(self) -> None:
        cache = InMemorySessionCache()
        await cache.delete("nonexistent")  # should not raise

    async def test_ttl_parameter_ignored(self) -> None:
        cache = InMemorySessionCache()
        await cache.set("key1", "value1", ttl_seconds=0)
        assert await cache.get("key1") == "value1"

    async def test_multiple_keys_independent(self) -> None:
        cache = InMemorySessionCache()
        await cache.set("a", "1")
        await cache.set("b", "2")
        assert await cache.get("a") == "1"
        assert await cache.get("b") == "2"
        await cache.delete("a")
        assert await cache.get("a") is None
        assert await cache.get("b") == "2"
