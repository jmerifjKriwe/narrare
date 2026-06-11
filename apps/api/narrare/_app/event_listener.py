"""Event listener that subscribes to Redis channels and routes to TaskIQ tasks.

Runs as a separate process or as part of the API server.
Infrastructure code — only used in the API layer (RULE-08).
"""

from __future__ import annotations

import json
from typing import Any, cast

# redis has no PEP 561 type stubs — use __import__ to avoid [import-untyped]
aioredis: Any = __import__("redis.asyncio", fromlist=["asyncio"])
import structlog  # noqa: E402

from narrare_core.events.types import EventType  # noqa: E402

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

        # self._pubsub is Any (redis has no stubs) — safe after None check
        assert self._pubsub is not None
        async for message in self._pubsub.listen():
            # Guard: pubsub messages are dict-like
            if not isinstance(message, dict):
                continue
            if cast("dict[str, Any]", message).get("type") != "message":
                continue

            try:
                raw_channel = cast("dict[str, Any]", message).get("channel")
                channel = (
                    raw_channel.decode()
                    if isinstance(raw_channel, bytes)
                    else str(raw_channel or "")
                )
                event_type = channel.removeprefix(_CHANNEL_PREFIX)
                raw_data = cast("dict[str, Any]", message).get("data")
                payload = json.loads(raw_data if isinstance(raw_data, (str, bytes)) else "{}")

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
            await self._pubsub.unsubscribe()
            await self._pubsub.aclose()
        logger.info("event_listener_stopped")
