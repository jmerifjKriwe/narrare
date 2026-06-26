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

logger = structlog.get_logger(__name__)

_CHANNEL_PREFIX = "narrare:events:"

# Map event types to registered TaskIQ task names (the ``task_name`` labels
# used at ``@broker.task(task_name=...)`` decoration time).
#
# Only events with a registered, compatible task are mapped. The EventListener
# is currently dormant infrastructure (not started by the application lifespan
# — see ``_app/lifespan.py``); ``_dispatch`` enqueues a single payload via
# ``task.kiq(payload)``, so when this listener is wired the dispatcher will
# need to adapt each event payload to its target task's signature.
#
# KB entry embedding is NOT routed here: the Redis Pub/Sub event payload
# lacks the entry content, while ``embed_source`` requires ``source_type``,
# ``source_id``, and ``content`` as kwargs. KB embedding is handled directly
# by ``EmbeddingHookManager._dispatch_task`` (kb/embedding_hooks.py), which
# has access to the entry content. This listener is infrastructure for
# future events whose payloads are self-contained.
_EVENT_TASK_MAP: dict[str, str] = {
    # CHAPTER_CONTENT_UPDATED → pending: no registered chapter-embedding task.
    # CHAPTER_DELETED → pending: no registered cleanup task.
}


class EventListener:
    """Listens to Redis Pub/Sub and enqueues TaskIQ tasks."""

    def __init__(self, redis_url: str, broker: Any | None = None) -> None:
        """Initialize the listener.

        Args:
            redis_url: Redis connection URL for Pub/Sub.
            broker: Optional TaskIQ broker used to enqueue tasks. When
                ``None``, the shared ``narrare.tasks.broker.broker`` is
                resolved lazily on first dispatch. Injecting a broker is
                primarily for testing.
        """
        self._redis_url = redis_url
        self._pubsub: Any = None
        self._broker: Any | None = broker

    def _get_broker(self) -> Any:
        """Return the broker, importing the shared one lazily if not injected."""
        if self._broker is None:
            # `narrare.tasks.broker` is a Phase 4+ module; import lazily to keep
            # the event-listener importable in environments without the broker.
            _broker_mod = __import__("narrare.tasks.broker", fromlist=["broker"])
            self._broker = _broker_mod.broker
        return self._broker

    async def _dispatch(self, event_type: str, payload: dict[str, Any]) -> None:
        """Look up and enqueue the TaskIQ task for a single event.

        Resolution: ``_EVENT_TASK_MAP`` maps an event type to a registered
        ``task_name`` label. If the task is not (yet) registered, the event is
        logged and skipped without raising — this keeps the listener resilient
        while tasks are wired up incrementally.
        """
        task_name = _EVENT_TASK_MAP.get(event_type)
        if not task_name:
            logger.debug("event_no_handler", event_type=event_type)
            return

        broker = self._get_broker()
        # broker is Any (taskiq has no stubs) — find_task returns the task or None.
        task = broker.find_task(task_name)
        if task is None:
            logger.warning(
                "event_task_not_registered",
                event_type=event_type,
                task=task_name,
            )
            return

        enqueued = await task.kiq(payload)
        logger.info(
            "event_enqueued",
            event_type=event_type,
            task=task_name,
            task_id=enqueued.task_id,
        )

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

                # Look up and enqueue the mapped TaskIQ task (graceful when
                # unmapped or not yet registered).
                await self._dispatch(event_type, payload)
            except Exception:
                logger.error("event_processing_failed", exc_info=True)

    async def stop(self) -> None:
        """Stop listening and clean up."""
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.aclose()
        logger.info("event_listener_stopped")
