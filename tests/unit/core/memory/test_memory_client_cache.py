"""Tests for memory/memory_client_cache.py — MemoryClientCache."""

from __future__ import annotations

from narrare_core.memory.memory_client_cache import MemoryClientCache


class TestMemoryClientCacheGet:
    """Tests for MemoryClientCache.get()."""

    def test_get_returns_none_for_missing_key(self) -> None:
        cache = MemoryClientCache()
        assert cache.get("user-1") is None

    def test_get_returns_cached_client(self) -> None:
        cache = MemoryClientCache()
        client = object()
        cache.put("user-1", client)
        assert cache.get("user-1") is client

    def test_get_moves_to_end_lru(self) -> None:
        """Accessing an entry moves it to the end (most recently used)."""
        cache = MemoryClientCache(max_size=2)
        cache.put("a", "client-a")
        cache.put("b", "client-b")
        # Access "a" to make it most recently used
        cache.get("a")
        # Adding "c" should evict "b" (least recently used), not "a"
        cache.put("c", "client-c")
        assert cache.get("a") is not None
        assert cache.get("b") is None
        assert cache.get("c") is not None


class TestMemoryClientCachePut:
    """Tests for MemoryClientCache.put()."""

    def test_put_stores_client(self) -> None:
        cache = MemoryClientCache()
        client = object()
        cache.put("user-1", client)
        assert cache.get("user-1") is client

    def test_put_overwrites_existing(self) -> None:
        cache = MemoryClientCache()
        old_client = object()
        new_client = object()
        cache.put("user-1", old_client)
        cache.put("user-1", new_client)
        assert cache.get("user-1") is new_client

    def test_put_evicts_oldest_when_full(self) -> None:
        cache = MemoryClientCache(max_size=2)
        cache.put("a", "client-a")
        cache.put("b", "client-b")
        cache.put("c", "client-c")  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None


class TestMemoryClientCacheInvalidate:
    """Tests for MemoryClientCache.invalidate()."""

    def test_invalidate_removes_entry(self) -> None:
        cache = MemoryClientCache()
        cache.put("user-1", "client")
        cache.invalidate("user-1")
        assert cache.get("user-1") is None

    def test_invalidate_nonexistent_is_noop(self) -> None:
        cache = MemoryClientCache()
        cache.invalidate("nonexistent")  # should not raise


class TestMemoryClientCacheClear:
    """Tests for MemoryClientCache.clear()."""

    def test_clear_removes_all_entries(self) -> None:
        cache = MemoryClientCache()
        cache.put("a", "client-a")
        cache.put("b", "client-b")
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_clear_on_empty_cache_is_noop(self) -> None:
        cache = MemoryClientCache()
        cache.clear()  # should not raise


class TestMemoryClientCacheMaxSize:
    """Tests for cache size limits."""

    def test_default_max_size(self) -> None:
        cache = MemoryClientCache()
        assert cache._max_size == 100

    def test_custom_max_size(self) -> None:
        cache = MemoryClientCache(max_size=5)
        assert cache._max_size == 5

    def test_cache_respects_max_size(self) -> None:
        cache = MemoryClientCache(max_size=3)
        for i in range(5):
            cache.put(f"user-{i}", f"client-{i}")
        # Only last 3 should remain
        assert cache.get("user-0") is None
        assert cache.get("user-1") is None
        assert cache.get("user-2") is not None
        assert cache.get("user-3") is not None
        assert cache.get("user-4") is not None
