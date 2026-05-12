"""Event listener that subscribes to Redis channels and routes to TaskIQ tasks.

Runs as a separate process or as part of the API server.
Infrastructure code — only used in the API layer (RULE-08).
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis  # type: ignore[import-untyped]
import structlog

from narrare_core.events.types import EventType

logger = structlog.get_logger(__name__)

_CHANNEL_PREFIX = "narrare:events:"

# Map event types to TaskIQ task names.
# Tasks will be implemented in Phase 5+ — for now we log the routing.
_EVENT_TASK_MAP: dict[str, str] = {
    EventType.CHAPTER_CONTENT_UPDATED: "narrare.tasks.embed_chapter_task",
    EventType.KB_ENTRY_UPDATED: "narrare.tasks.embed_kb_entry_task",
    EventType.CHAPTER_DELETED: "narrare.tasks.cleanup_chapter_task",
}


class EventListener:
    """Listens to Redis Pub/Sub and enqueues TaskIQ tasks."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._pubsub: Any = None

    async def start(self) -> None:
        """Start listening to event channels."""
        r: Any = aioredis.from_url(self._redis_url)
        self._pubsub = r.pubsub()

        channels = [f"{_CHANNEL_PREFIX}{et}" for et in _EVENT_TASK_MAP]
        await self._pubsub.subscribe(*channels)

        logger.info("event_listener_started", channels=channels)

    async def listen(self) -> None:
        """Main listen loop — blocks until stopped.

        Raises:
            RuntimeError: If called before ``start()``.
        """
        if not self._pubsub:
            raise RuntimeError("Listener not started. Call start() first.")

        async for message in self._pubsub.listen():  # type: ignore[union-attr]
            if message["type"] != "message":  # type: ignore[index]
                continue

            try:
                raw_channel = message["channel"]  # type: ignore[index]
                channel = raw_channel.decode() if isinstance(raw_channel, bytes) else raw_channel
                event_type = channel.removeprefix(_CHANNEL_PREFIX)
                payload = json.loads(message["data"])  # type: ignore[index]

                task_name = _EVENT_TASK_MAP.get(event_type)
                if not task_name:
                    logger.debug("event_no_handler", event_type=event_type)
                    continue

                # For now, log the event. TaskIQ task enqueueing will be
                # implemented when the actual tasks exist in Phase 5.
                logger.info(
                    "event_received",
                    event_type=event_type,
                    task=task_name,
                    aggregate_id=payload.get("aggregate_id"),
                )
            except Exception:
                logger.error("event_processing_failed", exc_info=True)

    async def stop(self) -> None:
        """Stop listening and clean up."""
        if self._pubsub:
            await self._pubsub.unsubscribe()  # type: ignore[union-attr]
            await self._pubsub.aclose()  # type: ignore[union-attr]
        logger.info("event_listener_stopped")
