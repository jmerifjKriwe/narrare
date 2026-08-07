"""Tests for InMemorySessionCache — TTL-capable in-process session cache.

Tests cover:
- Structural protocol compliance (SessionCacheProtocol)
- Happy path for get, set (with and without TTL), delete
- Real TTL expiration (lazy expiry-on-access)
- ``ttl_seconds=None`` → no expiry (for WebSocket session usage)
- Cleanup of expired entries (no unbounded growth)

Time is controlled via an injectable fake clock — no real sleeping.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import pytest

from narrare_core.cache import InMemorySessionCache
from narrare_core.writing.session_manager import SessionManager

if TYPE_CHECKING:
    from narrare_core.writing.session_manager import SessionCacheProtocol


# ---------------------------------------------------------------------------
# Test-only fake clock — keeps test-only code out of the production class
# ---------------------------------------------------------------------------


class FakeClock:
    """Deterministic monotonic clock for TTL tests."""

    def __init__(self) -> None:
        self._now: float = 0.0

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def cache(clock: FakeClock) -> InMemorySessionCache:
    """InMemorySessionCache wired to the deterministic fake clock."""
    return InMemorySessionCache(clock=clock)


# ---------------------------------------------------------------------------
# Structural: protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """InMemorySessionCache structurally satisfies SessionCacheProtocol."""

    async def test_get_returns_str_or_none(self, cache: InMemorySessionCache) -> None:
        """get() returns a str (or None when missing)."""
        result = await cache.get("missing")
        assert result is None
        await cache.set("k", "v")
        result = await cache.get("k")
        assert isinstance(result, str)

    async def test_set_accepts_optional_ttl(self, cache: InMemorySessionCache) -> None:
        """set() accepts (key, value) and (key, value, ttl_seconds)."""
        await cache.set("a", "1")  # no TTL — must not raise
        await cache.set("b", "2", ttl_seconds=300)  # with TTL — must not raise
        assert await cache.get("a") == "1"
        assert await cache.get("b") == "2"

    async def test_delete_accepts_str(self, cache: InMemorySessionCache) -> None:
        """delete() accepts a key and removes it."""
        await cache.set("k", "v")
        await cache.delete("k")
        assert await cache.get("k") is None


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestGet:
    """Tests for InMemorySessionCache.get()."""

    async def test_returns_stored_value(self, cache: InMemorySessionCache) -> None:
        await cache.set("greeting", "hello")
        assert await cache.get("greeting") == "hello"

    async def test_returns_none_on_miss(self, cache: InMemorySessionCache) -> None:
        assert await cache.get("missing") is None

    async def test_returns_latest_value_after_overwrite(self, cache: InMemorySessionCache) -> None:
        await cache.set("k", "first")
        await cache.set("k", "second")
        assert await cache.get("k") == "second"


class TestSet:
    """Tests for InMemorySessionCache.set()."""

    async def test_set_without_ttl_persists(
        self, cache: InMemorySessionCache, clock: FakeClock
    ) -> None:
        """set() without ttl_seconds keeps the value forever."""
        await cache.set("k", "v")
        clock.advance(10_000)
        assert await cache.get("k") == "v"

    async def test_set_with_ttl_stores_value(self, cache: InMemorySessionCache) -> None:
        """set() with ttl_seconds stores the value until expiry."""
        await cache.set("k", "v", ttl_seconds=60)
        assert await cache.get("k") == "v"


class TestDelete:
    """Tests for InMemorySessionCache.delete()."""

    async def test_delete_existing_key(self, cache: InMemorySessionCache) -> None:
        await cache.set("k", "v")
        await cache.delete("k")
        assert await cache.get("k") is None

    async def test_delete_missing_key_is_silent(self, cache: InMemorySessionCache) -> None:
        """delete() succeeds silently for a non-existent key."""
        await cache.delete("never_set")  # must not raise


# ---------------------------------------------------------------------------
# TTL expiration — real expiry, not "TTL ignored"
# ---------------------------------------------------------------------------


class TestTTLExpiry:
    """Real TTL expiration via lazy expiry-on-access."""

    async def test_value_expires_after_ttl(
        self, cache: InMemorySessionCache, clock: FakeClock
    ) -> None:
        """get() returns None once ttl_seconds has elapsed."""
        await cache.set("k", "v", ttl_seconds=10)
        clock.advance(10)
        assert await cache.get("k") is None

    async def test_value_present_before_ttl(
        self, cache: InMemorySessionCache, clock: FakeClock
    ) -> None:
        """get() returns the value while ttl_seconds has not elapsed."""
        await cache.set("k", "v", ttl_seconds=10)
        clock.advance(9)
        assert await cache.get("k") == "v"

    async def test_expired_entry_is_evicted_from_store(
        self, cache: InMemorySessionCache, clock: FakeClock
    ) -> None:
        """Accessing an expired key removes it (no zombie entries)."""
        await cache.set("k", "v", ttl_seconds=10)
        clock.advance(10)
        assert await cache.get("k") is None
        # The expired entry must not linger in the backing store.
        assert "k" not in cache._store

    async def test_ttl_refreshed_on_overwrite(
        self, cache: InMemorySessionCache, clock: FakeClock
    ) -> None:
        """Re-setting a key with a new TTL resets the expiry window."""
        await cache.set("k", "v", ttl_seconds=10)
        clock.advance(9)  # 1 second of life left
        await cache.set("k", "v", ttl_seconds=10)  # refresh
        clock.advance(9)  # 1 second of the new window left
        assert await cache.get("k") == "v"

    async def test_overwrite_no_ttl_makes_entry_persistent(
        self, cache: InMemorySessionCache, clock: FakeClock
    ) -> None:
        """Re-setting with ttl_seconds=None removes the expiry."""
        await cache.set("k", "v", ttl_seconds=10)
        await cache.set("k", "v")  # now persistent
        clock.advance(10_000)
        assert await cache.get("k") == "v"


# ---------------------------------------------------------------------------
# ttl_seconds=None → no expiry (WebSocket session usage)
# ---------------------------------------------------------------------------


class TestNoExpiry:
    """ttl_seconds=None means the entry never expires."""

    async def test_none_ttl_does_not_expire(
        self, cache: InMemorySessionCache, clock: FakeClock
    ) -> None:
        await cache.set("session", "state")
        clock.advance(86_400)  # a day
        assert await cache.get("session") == "state"


# ---------------------------------------------------------------------------
# Cleanup — no unbounded growth of expired entries
# ---------------------------------------------------------------------------


class TestPurge:
    """Expired entries are cleaned up so the store cannot grow unbounded."""

    async def test_write_purges_other_expired_entries(
        self, cache: InMemorySessionCache, clock: FakeClock
    ) -> None:
        """A new write sweeps entries whose TTL has already elapsed."""
        await cache.set("a", "1", ttl_seconds=10)
        await cache.set("b", "2", ttl_seconds=10)
        clock.advance(10)  # both a and b now expired

        await cache.set("c", "3")  # triggers a sweep

        assert await cache.get("a") is None
        assert await cache.get("b") is None
        assert await cache.get("c") == "3"
        # Only the live entry remains.
        assert len(cache._store) == 1

    async def test_live_entries_survive_purge(
        self, cache: InMemorySessionCache, clock: FakeClock
    ) -> None:
        """A sweep must not remove entries whose TTL has not elapsed."""
        await cache.set("a", "1", ttl_seconds=100)
        await cache.set("b", "2", ttl_seconds=10)
        clock.advance(10)  # only b expired

        await cache.set("c", "3")  # triggers a sweep

        assert await cache.get("a") == "1"  # still alive
        assert await cache.get("b") is None
        assert await cache.get("c") == "3"


# ---------------------------------------------------------------------------
# Structural typing — duck typing satisfies SessionCacheProtocol
# ---------------------------------------------------------------------------


class TestStructuralTyping:
    """InMemorySessionCache is structurally compatible with SessionCacheProtocol."""

    async def test_methods_match_protocol_shape(self) -> None:
        """Method signatures match SessionCacheProtocol."""
        c = InMemorySessionCache()

        assert hasattr(c, "get")
        assert hasattr(c, "set")
        assert hasattr(c, "delete")

        assert inspect.iscoroutinefunction(c.get)
        assert inspect.iscoroutinefunction(c.set)
        assert inspect.iscoroutinefunction(c.delete)

        sig_get = inspect.signature(c.get)
        assert list(sig_get.parameters) == ["key"]

        sig_set = inspect.signature(c.set)
        assert list(sig_set.parameters) == ["key", "value", "ttl_seconds"]
        assert sig_set.parameters["ttl_seconds"].default is None

        sig_delete = inspect.signature(c.delete)
        assert list(sig_delete.parameters) == ["key"]

    async def test_session_manager_accepts_in_memory_cache(
        self, cache: InMemorySessionCache
    ) -> None:
        """SessionManager accepts InMemorySessionCache as its cache backend."""
        mgr = SessionManager(cache=cache)
        assert mgr._cache is cache

    def test_satisfies_protocol_at_type_check_time(self) -> None:
        """Static conformance: assign to a SessionCacheProtocol annotation.

        This is a runtime no-op that mypy/pyright verify at type-check time.
        """
        cache: SessionCacheProtocol = InMemorySessionCache()
        assert cache is not None
