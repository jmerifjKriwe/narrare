"""Unit tests for the WS session cache — re-export of core/cache's InMemorySessionCache.

``narrare.writing._ws_cache`` is now a thin re-export of
:class:`~narrare_core.cache.InMemorySessionCache` (ADR-080, RULE-08).
WebSocket sessions use it in **no-expiry mode** (the default
``ttl_seconds=None``): entries persist for the process lifetime and are
never evicted by TTL. These tests cover the no-TTL WS use case plus a
regression guard that the Core implementation — unlike the old local
stub — honours an explicit TTL.
"""

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

    async def test_no_ttl_persists_indefinitely(self) -> None:
        """WS sessions use the default no-TTL mode: entries never expire."""
        cache = InMemorySessionCache()
        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

    async def test_explicit_ttl_is_honored(self) -> None:
        """Regression guard: the Core re-export honours TTL (ADR-080).

        Unlike the old local ``_ws_cache`` stub that ignored TTL, the
        consolidated Core implementation expires entries when a TTL is
        given. ``ttl_seconds=0`` means immediate expiry. WS sessions must
        therefore rely on the default (no TTL) rather than passing one.
        """
        cache = InMemorySessionCache()
        await cache.set("key1", "value1", ttl_seconds=0)
        assert await cache.get("key1") is None

    async def test_multiple_keys_independent(self) -> None:
        cache = InMemorySessionCache()
        await cache.set("a", "1")
        await cache.set("b", "2")
        assert await cache.get("a") == "1"
        assert await cache.get("b") == "2"
        await cache.delete("a")
        assert await cache.get("a") is None
        assert await cache.get("b") == "2"
