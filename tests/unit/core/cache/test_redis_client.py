"""Tests for RedisSessionCache — Redis-backed session cache.

Tests cover:
- Structural protocol compliance (duck typing for SessionCacheProtocol)
- Happy path for get, set (with and without TTL), delete
- Graceful degradation when Redis is unreachable
- Lazy client initialisation
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest

from narrare_core.cache.redis_client import RedisSessionCache

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def redis_url() -> str:
    return "redis://example.com:6379/0"


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Return a mock Redis client with async methods."""
    client = MagicMock(spec=["get", "set", "setex", "delete"])
    client.get = AsyncMock(return_value="cached_value")
    client.set = AsyncMock()
    client.setex = AsyncMock()
    client.delete = AsyncMock()
    return client


@pytest.fixture
def cache(
    redis_url: str,
    mock_redis_client: MagicMock,
) -> Generator[RedisSessionCache]:
    """RedisSessionCache with a pre-mocked client."""
    with patch("redis.asyncio.from_url", return_value=mock_redis_client):
        c = RedisSessionCache(redis_url)
        yield c


@pytest.fixture
def unreachable_cache(
    redis_url: str,
) -> Generator[RedisSessionCache]:
    """RedisSessionCache whose client raises on every call."""
    err_client = MagicMock(spec=["get", "set", "setex", "delete"])
    err_client.get = AsyncMock(side_effect=ConnectionError("Redis unreachable"))
    err_client.set = AsyncMock(side_effect=ConnectionError("Redis unreachable"))
    err_client.setex = AsyncMock(side_effect=ConnectionError("Redis unreachable"))
    err_client.delete = AsyncMock(side_effect=ConnectionError("Redis unreachable"))

    with patch("redis.asyncio.from_url", return_value=err_client):
        c = RedisSessionCache(redis_url)
        yield c


# ---------------------------------------------------------------------------
# Structural: protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """Verify RedisSessionCache structurally satisfies SessionCacheProtocol."""

    async def test_has_get(self, cache: RedisSessionCache) -> None:
        """get() returns str | None."""
        result = await cache.get("some_key")
        assert isinstance(result, str) or result is None

    async def test_has_set(self, cache: RedisSessionCache) -> None:
        """set() accepts str and optional TTL."""
        await cache.set("key", "value")
        await cache.set("key", "value", ttl_seconds=300)
        assert True

    async def test_has_delete(self, cache: RedisSessionCache) -> None:
        """delete() accepts str."""
        await cache.delete("some_key")
        assert True


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestGet:
    """Tests for RedisSessionCache.get()."""

    async def test_returns_cached_value(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """get() returns the value stored in Redis."""
        mock_redis_client.get.return_value = "hello"
        result = await cache.get("greeting")
        assert result == "hello"
        mock_redis_client.get.assert_awaited_once_with("greeting")

    async def test_returns_none_on_miss(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """get() returns None when the key is not in Redis."""
        mock_redis_client.get.return_value = None
        result = await cache.get("missing")
        assert result is None

    async def test_client_is_cached_after_first_call(self, cache: RedisSessionCache) -> None:
        """_get_client() returns the same client on subsequent calls."""
        client1 = await cache._get_client()
        client2 = await cache._get_client()
        assert client1 is client2


class TestSet:
    """Tests for RedisSessionCache.set()."""

    async def test_set_without_ttl(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """set() without ttl_seconds uses SET (not SETEX)."""
        await cache.set("key", "value")
        mock_redis_client.set.assert_awaited_once_with("key", "value")
        mock_redis_client.setex.assert_not_awaited()

    async def test_set_with_ttl(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """set() with ttl_seconds uses SETEX."""
        await cache.set("key", "value", ttl_seconds=60)
        mock_redis_client.setex.assert_awaited_once_with("key", 60, "value")
        mock_redis_client.set.assert_not_awaited()

    async def test_set_zero_ttl(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """set() with ttl_seconds=0 uses SETEX (valid Redis TTL)."""
        await cache.set("key", "value", ttl_seconds=0)
        mock_redis_client.setex.assert_awaited_once_with("key", 0, "value")
        mock_redis_client.set.assert_not_awaited()


class TestDelete:
    """Tests for RedisSessionCache.delete()."""

    async def test_delete_existing_key(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """delete() calls Redis DEL for an existing key."""
        await cache.delete("some_key")
        mock_redis_client.delete.assert_awaited_once_with("some_key")

    async def test_delete_missing_key(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """delete() succeeds silently for a non-existent key."""
        mock_redis_client.delete.return_value = 0
        await cache.delete("missing_key")
        mock_redis_client.delete.assert_awaited_once_with("missing_key")


# ---------------------------------------------------------------------------
# Error path — graceful degradation
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """All cache methods degrade gracefully when Redis is unreachable."""

    async def test_get_returns_none_on_redis_error(
        self, unreachable_cache: RedisSessionCache
    ) -> None:
        """get() returns None when Redis raises a connection error."""
        result = await unreachable_cache.get("any")
        assert result is None

    async def test_get_returns_none_on_generic_error(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """get() returns None on any exception type."""
        mock_redis_client.get.side_effect = RuntimeError("Unexpected")
        result = await cache.get("any")
        assert result is None

    async def test_get_recovers_after_transient_error(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """get() recovers after a transient failure (client persists)."""
        mock_redis_client.get.side_effect = ConnectionError("Transient")
        assert await cache.get("key") is None
        mock_redis_client.get.side_effect = None
        mock_redis_client.get.return_value = "recovered"
        assert await cache.get("key") == "recovered"

    async def test_set_silent_on_redis_error(self, unreachable_cache: RedisSessionCache) -> None:
        """set() does not raise when Redis is unreachable."""
        await unreachable_cache.set("any", "value")
        assert True

    async def test_set_with_ttl_silent_on_error(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """set() with TTL does not raise on exception."""
        mock_redis_client.setex.side_effect = RuntimeError("Unexpected")
        await cache.set("key", "value", ttl_seconds=60)
        assert True

    async def test_delete_silent_on_redis_error(self, unreachable_cache: RedisSessionCache) -> None:
        """delete() does not raise when Redis is unreachable."""
        await unreachable_cache.delete("any")
        assert True

    async def test_delete_silent_on_generic_error(
        self, cache: RedisSessionCache, mock_redis_client: MagicMock
    ) -> None:
        """delete() does not raise on any exception."""
        mock_redis_client.delete.side_effect = RuntimeError("Unexpected")
        await cache.delete("key")
        assert True


# ---------------------------------------------------------------------------
# Lazy initialization
# ---------------------------------------------------------------------------


class TestLazyInit:
    """Redis client is not created until first use."""

    async def test_no_client_before_first_call(self, redis_url: str) -> None:
        """_redis is None after construction."""
        c = RedisSessionCache(redis_url)
        assert c._redis is None

    async def test_import_happens_on_first_get(self, redis_url: str) -> None:
        """redis.asyncio is imported on the first method call."""
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = MagicMock(spec=["get"])
            mock_client.get = AsyncMock(return_value="val")
            mock_from_url.return_value = mock_client

            c = RedisSessionCache(redis_url)
            result = await c.get("key")
            assert result == "val"
            mock_from_url.assert_called_once_with(redis_url, decode_responses=True)

    async def test_decode_responses_true(self, redis_url: str) -> None:
        """Client created with decode_responses=True."""
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = MagicMock(spec=["get"])
            mock_client.get = AsyncMock(return_value="val")
            mock_from_url.return_value = mock_client

            c = RedisSessionCache(redis_url)
            await c.get("key")
            mock_from_url.assert_called_once_with(redis_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Structural type check: duck typing satisfies SessionCacheProtocol
# ---------------------------------------------------------------------------


class TestStructuralTyping:
    """Ensure RedisSessionCache is structurally compatible with Protocol."""

    async def test_can_be_used_as_cache_protocol(self) -> None:
        """Method signatures match SessionCacheProtocol."""
        import inspect

        c = RedisSessionCache("redis://localhost:6379/0")

        assert hasattr(c, "get")
        assert hasattr(c, "set")
        assert hasattr(c, "delete")

        assert inspect.iscoroutinefunction(c.get)
        assert inspect.iscoroutinefunction(c.set)
        assert inspect.iscoroutinefunction(c.delete)

        sig_get = inspect.signature(c.get)
        assert "key" in sig_get.parameters

        sig_set = inspect.signature(c.set)
        assert "key" in sig_set.parameters
        assert "value" in sig_set.parameters
        assert "ttl_seconds" in sig_set.parameters

        sig_delete = inspect.signature(c.delete)
        assert "key" in sig_delete.parameters

    async def test_session_manager_accepts_redis_cache(self, cache: RedisSessionCache) -> None:
        """SessionManager accepts RedisSessionCache as cache backend."""
        from narrare_core.writing.session_manager import SessionManager

        mgr = SessionManager(cache=cache)
        assert mgr._cache is cache
