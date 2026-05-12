"""Redis Pub/Sub event bus implementation.

Uses Redis for event publishing and provides integration hooks for TaskIQ.
Infrastructure code — only used in the API layer (RULE-08).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import redis.asyncio as aioredis  # type: ignore[import-untyped]
import structlog

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from narrare_core.events.types import DomainEvent, EventType

logger = structlog.get_logger(__name__)

_CHANNEL_PREFIX = "narrare:events:"


class RedisEventBus:
    """Event bus backed by Redis Pub/Sub.

    Events are published to Redis channels named ``narrare:events:{event_type}``.
    Subscribers listen on specific channels and route to TaskIQ tasks.
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: Any = None

    async def start(self) -> None:
        """Initialize Redis connection."""
        self._redis = aioredis.from_url(self._redis_url)
        logger.info("event_bus_started")

    async def stop(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
        logger.info("event_bus_stopped")

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to Redis.

        Silently returns if the bus hasn't been started yet.
        Logs errors but never raises — event publishing must not block
        the main operation.
        """
        if not self._redis:
            logger.warning("event_bus_not_started", event_type=event.event_type)
            return

        channel = f"{_CHANNEL_PREFIX}{event.event_type}"
        payload = self._serialize(event)

        try:
            await self._redis.publish(channel, json.dumps(payload))
            logger.debug(
                "event_published",
                event_type=event.event_type,
                aggregate_id=str(event.aggregate_id),
            )
        except Exception:
            logger.error("event_publish_failed", event_type=event.event_type, exc_info=True)

    async def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[DomainEvent], Awaitable[None]],
    ) -> None:
        """Subscribe to an event type.

        Note: For TaskIQ integration, use task decorators instead.
        This is for custom async handlers.
        """
        # Pub/Sub subscription is handled by the EventListener process.

    @staticmethod
    def _serialize(event: DomainEvent) -> dict[str, object]:
        """Convert a DomainEvent to a JSON-safe dict."""
        return {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "aggregate_id": str(event.aggregate_id),
            "payload": event.payload,
            "timestamp": event.timestamp.isoformat(),
            "correlation_id": event.correlation_id,
            "user_id": str(event.user_id) if event.user_id else None,
        }


# ---------------------------------------------------------------------------
# Singleton lifecycle — initialized in lifespan, consumed via get_event_bus
# ---------------------------------------------------------------------------

_event_bus: RedisEventBus | None = None


def get_event_bus() -> RedisEventBus:
    """Get the global event bus instance.

    Raises:
        RuntimeError: If the bus hasn't been initialized yet.
    """
    if _event_bus is None:
        raise RuntimeError("Event bus not initialized. Call init_event_bus() first.")
    return _event_bus


async def init_event_bus(redis_url: str) -> RedisEventBus:
    """Initialize and start the global event bus."""
    global _event_bus
    _event_bus = RedisEventBus(redis_url)
    await _event_bus.start()
    return _event_bus


async def shutdown_event_bus() -> None:
    """Shutdown the global event bus."""
    global _event_bus
    if _event_bus:
        await _event_bus.stop()
        _event_bus = None
