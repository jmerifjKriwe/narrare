"""Unit tests for ``narrare._app.events`` — RedisEventBus and module lifecycle.

Tests the event bus logic with mocked Redis so no real Redis connection
is needed. Covers:
- ``RedisEventBus`` constructor, start, stop, publish, serialize
- Module-level ``get_event_bus()``, ``init_event_bus()``, ``shutdown_event_bus()``
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare._app.events import (
    RedisEventBus,
    get_event_bus,
    init_event_bus,
    shutdown_event_bus,
)
from narrare_core.events.types import DomainEvent, EventType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(**overrides: object) -> DomainEvent:
    """Create a minimal DomainEvent for testing."""
    defaults: dict[str, object] = {
        "event_type": EventType.CHAPTER_CREATED,
        "aggregate_id": uuid4(),
        "payload": {"title": "Chapter 1"},
        "user_id": uuid4(),
    }
    defaults.update(overrides)
    return DomainEvent(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RedisEventBus — constructor
# ---------------------------------------------------------------------------


def test_event_bus_constructor() -> None:
    """Constructor stores redis_url and sets _redis to None."""
    bus = RedisEventBus("redis://localhost:6379")
    assert bus._redis_url == "redis://localhost:6379"
    assert bus._redis is None


# ---------------------------------------------------------------------------
# RedisEventBus — start / stop
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_event_bus_start() -> None:
    """start() creates a Redis client from the URL."""
    mock_redis = MagicMock(spec=object)
    with patch("narrare._app.events.aioredis") as mock_aioredis:
        mock_aioredis.from_url = MagicMock(spec=object, return_value=mock_redis)
        bus = RedisEventBus("redis://test:6379")
        await bus.start()

    assert bus._redis is mock_redis


@pytest.mark.anyio
async def test_event_bus_stop_closes_connection() -> None:
    """stop() closes the Redis connection and resets _redis to None."""
    mock_redis = MagicMock(spec=object)
    mock_redis.aclose = AsyncMock()

    bus = RedisEventBus("redis://test:6379")
    bus._redis = mock_redis
    await bus.stop()

    mock_redis.aclose.assert_awaited_once()
    assert bus._redis is None


@pytest.mark.anyio
async def test_event_bus_stop_noop_when_not_started() -> None:
    """stop() is a no-op when _redis is already None."""
    bus = RedisEventBus("redis://test:6379")
    # Should not raise
    await bus.stop()


# ---------------------------------------------------------------------------
# RedisEventBus — publish
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_event_bus_publish_not_started() -> None:
    """publish() silently returns when bus hasn't been started."""
    bus = RedisEventBus("redis://test:6379")
    event = _make_event()
    # Should not raise
    await bus.publish(event)


@pytest.mark.anyio
async def test_event_bus_publish_success() -> None:
    """publish() sends serialized event to the correct Redis channel."""
    mock_redis = MagicMock(spec=object)
    mock_redis.publish = AsyncMock()

    bus = RedisEventBus("redis://test:6379")
    bus._redis = mock_redis

    event = _make_event()
    await bus.publish(event)

    channel = f"narrare:events:{event.event_type}"
    expected_payload = json.dumps(RedisEventBus._serialize(event))
    mock_redis.publish.assert_awaited_once_with(channel, expected_payload)


@pytest.mark.anyio
async def test_event_bus_publish_handles_redis_error() -> None:
    """publish() logs but does not raise when Redis publish fails."""
    mock_redis = MagicMock(spec=object)
    mock_redis.publish = AsyncMock(side_effect=ConnectionError("redis down"))

    bus = RedisEventBus("redis://test:6379")
    bus._redis = mock_redis

    event = _make_event()
    # Should NOT raise
    await bus.publish(event)


# ---------------------------------------------------------------------------
# RedisEventBus — _serialize
# ---------------------------------------------------------------------------


def test_event_bus_serialize() -> None:
    """_serialize() produces a JSON-safe dict from a DomainEvent."""
    event_id = uuid4()
    agg_id = uuid4()
    user_id = uuid4()
    ts = datetime.now(UTC)

    event = DomainEvent(
        event_type=EventType.CHAPTER_CONTENT_UPDATED,
        aggregate_id=agg_id,
        payload={"key": "value"},
        event_id=event_id,
        timestamp=ts,
        correlation_id="corr-123",
        user_id=user_id,
    )

    result = RedisEventBus._serialize(event)

    assert result["event_id"] == str(event_id)
    assert result["event_type"] == EventType.CHAPTER_CONTENT_UPDATED
    assert result["aggregate_id"] == str(agg_id)
    assert result["payload"] == {"key": "value"}
    assert result["timestamp"] == ts.isoformat()
    assert result["correlation_id"] == "corr-123"
    assert result["user_id"] == str(user_id)


def test_event_bus_serialize_no_user_id() -> None:
    """_serialize() returns None for user_id when not set."""
    event = _make_event(user_id=None)
    result = RedisEventBus._serialize(event)
    assert result["user_id"] is None


# ---------------------------------------------------------------------------
# Module-level lifecycle
# ---------------------------------------------------------------------------


def test_get_event_bus_raises_when_not_initialized() -> None:
    """get_event_bus() raises RuntimeError when bus hasn't been initialized."""
    import narrare._app.events as events_mod

    # Save and restore module state
    original = events_mod._event_bus
    events_mod._event_bus = None
    try:
        with pytest.raises(RuntimeError, match="Event bus not initialized"):
            get_event_bus()
    finally:
        events_mod._event_bus = original


@pytest.mark.anyio
async def test_init_and_shutdown_event_bus() -> None:
    """init_event_bus() creates and starts a bus; shutdown_event_bus() stops it."""
    import narrare._app.events as events_mod

    original = events_mod._event_bus

    mock_redis = MagicMock(spec=object)
    mock_redis.aclose = AsyncMock()

    with patch("narrare._app.events.aioredis") as mock_aioredis:
        mock_aioredis.from_url = MagicMock(spec=object, return_value=mock_redis)

        try:
            bus = await init_event_bus("redis://test:6379")
            assert bus is not None
            assert get_event_bus() is bus

            await shutdown_event_bus()
            # After shutdown, bus should be None
        finally:
            events_mod._event_bus = original
