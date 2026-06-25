"""Unit tests for ``narrare._app.event_listener`` — EventListener.

Tests the Redis Pub/Sub event listener logic with fake classes so no
real Redis connection is needed.  Covers:
- ``EventListener`` constructor, start, listen, stop
- Message processing: valid messages, non-dict skip, non-message skip,
  unknown event type, JSON decode errors, string channels
- Error guard: ``listen()`` before ``start()`` raises RuntimeError
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from narrare._app.event_listener import _CHANNEL_PREFIX, _EVENT_TASK_MAP, EventListener
from narrare_core.events.types import EventType

# ---------------------------------------------------------------------------
# Fake Redis objects (no MagicMock — pure Python fakes)
# ---------------------------------------------------------------------------


class _FakePubSub:
    """Fake Redis PubSub that yields a predefined list of messages."""

    def __init__(self, messages: list[Any] | None = None) -> None:
        self._messages: list[Any] = list(messages or [])
        self.subscribed_channels: list[str] = []
        self.unsubscribed: bool = False
        self.closed: bool = False

    async def subscribe(self, *channels: str) -> None:
        self.subscribed_channels.extend(channels)

    async def listen(self):  # type: ignore[override]
        for msg in self._messages:
            yield msg

    async def unsubscribe(self) -> None:
        self.unsubscribed = True

    async def aclose(self) -> None:
        self.closed = True


class _FakeRedis:
    """Fake Redis client returning a shared PubSub object."""

    def __init__(self, pubsub: _FakePubSub) -> None:
        self._pubsub = pubsub

    def pubsub(self) -> _FakePubSub:
        return self._pubsub


class _FakeAioRedis:
    """Fake ``redis.asyncio`` module for patching."""

    def __init__(self, redis: _FakeRedis) -> None:
        self._redis = redis

    def from_url(self, _url: str) -> _FakeRedis:
        return self._redis


def _wire_listener(
    monkeypatch: pytest.MonkeyPatch,
    messages: list[Any] | None = None,
) -> tuple[EventListener, _FakePubSub]:
    """Create an EventListener with a wired-up fake Redis stack.

    A no-op fake broker is injected so dispatch never touches the real TaskIQ
    broker or Redis (these tests cover message parsing, not real enqueueing).
    """
    pubsub = _FakePubSub(messages=messages)
    fake_redis = _FakeRedis(pubsub)

    import narrare._app.event_listener as mod

    monkeypatch.setattr(mod, "aioredis", _FakeAioRedis(fake_redis))

    listener = EventListener("redis://test:6379", broker=_FakeBroker(task=None))
    return listener, pubsub


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestEventListenerConstructor:
    def test_stores_redis_url(self) -> None:
        listener = EventListener("redis://localhost:6379")
        assert listener._redis_url == "redis://localhost:6379"

    def test_pubsub_starts_none(self) -> None:
        listener = EventListener("redis://localhost:6379")
        assert listener._pubsub is None


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------


class TestEventListenerStart:
    async def test_start_creates_pubsub_and_subscribes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        listener, pubsub = _wire_listener(monkeypatch)

        await listener.start()

        assert listener._pubsub is pubsub
        # Should subscribe to all channels in _EVENT_TASK_MAP
        assert len(pubsub.subscribed_channels) == len(_EVENT_TASK_MAP)
        for channel in pubsub.subscribed_channels:
            assert channel.startswith(_CHANNEL_PREFIX)


# ---------------------------------------------------------------------------
# listen()
# ---------------------------------------------------------------------------


class TestEventListenerListen:
    async def test_listen_raises_before_start(self) -> None:
        listener = EventListener("redis://test:6379")
        with pytest.raises(RuntimeError, match="not started"):
            await listener.listen()

    async def test_listen_processes_valid_bytes_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        channel = f"{_CHANNEL_PREFIX}{EventType.CHAPTER_CONTENT_UPDATED}"
        payload = json.dumps({"aggregate_id": "ch-123"}).encode()
        messages = [
            {"type": "message", "channel": channel.encode(), "data": payload},
        ]

        listener, _ = _wire_listener(monkeypatch, messages=messages)
        await listener.start()
        # Should complete without raising
        await listener.listen()

    async def test_listen_processes_valid_string_channel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Channel as string (not bytes) is handled correctly."""
        channel = f"{_CHANNEL_PREFIX}{EventType.KB_ENTRY_UPDATED}"
        messages = [
            {"type": "message", "channel": channel, "data": "{}"},
        ]

        listener, _ = _wire_listener(monkeypatch, messages=messages)
        await listener.start()
        await listener.listen()

    async def test_listen_skips_non_dict_messages(self, monkeypatch: pytest.MonkeyPatch) -> None:
        messages: list[Any] = ["not-a-dict", 42, None]

        listener, _ = _wire_listener(monkeypatch, messages=messages)
        await listener.start()
        await listener.listen()

    async def test_listen_skips_non_message_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Messages with type != 'message' (e.g. subscribe) are skipped."""
        messages = [
            {"type": "subscribe", "channel": b"foo", "data": 1},
            {"type": "message", "channel": b"foo", "data": 1},  # unknown event
        ]

        listener, _ = _wire_listener(monkeypatch, messages=messages)
        await listener.start()
        await listener.listen()

    async def test_listen_skips_unknown_event_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown event type logs debug and continues."""
        channel = f"{_CHANNEL_PREFIX}UNKNOWN_EVENT"
        messages = [
            {"type": "message", "channel": channel.encode(), "data": b"{}"},
        ]

        listener, _ = _wire_listener(monkeypatch, messages=messages)
        await listener.start()
        await listener.listen()

    async def test_listen_handles_json_decode_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Malformed JSON in message data is caught and logged."""
        channel = f"{_CHANNEL_PREFIX}{EventType.CHAPTER_DELETED}"
        messages = [
            {"type": "message", "channel": channel.encode(), "data": b"not-json"},
        ]

        listener, _ = _wire_listener(monkeypatch, messages=messages)
        await listener.start()
        await listener.listen()

    async def test_listen_handles_none_channel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Channel of None is handled gracefully (becomes empty string)."""
        channel = f"{_CHANNEL_PREFIX}{EventType.CHAPTER_CONTENT_UPDATED}"
        messages = [
            {"type": "message", "channel": None, "data": b"{}"},
            {"type": "message", "channel": channel.encode(), "data": b"{}"},
        ]

        listener, _ = _wire_listener(monkeypatch, messages=messages)
        await listener.start()
        await listener.listen()

    async def test_listen_handles_non_bytes_non_str_data(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-str/bytes data falls back to '{}' for json.loads."""
        channel = f"{_CHANNEL_PREFIX}{EventType.CHAPTER_CONTENT_UPDATED}"
        messages = [
            {"type": "message", "channel": channel.encode(), "data": 12345},
        ]

        listener, _ = _wire_listener(monkeypatch, messages=messages)
        await listener.start()
        await listener.listen()


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------


class TestEventListenerStop:
    async def test_stop_cleans_up(self, monkeypatch: pytest.MonkeyPatch) -> None:
        listener, pubsub = _wire_listener(monkeypatch)
        await listener.start()

        await listener.stop()

        assert pubsub.unsubscribed
        assert pubsub.closed

    async def test_stop_noop_when_not_started(self) -> None:
        listener = EventListener("redis://test:6379")
        # Should not raise
        await listener.stop()


# ---------------------------------------------------------------------------
# _dispatch() — event → TaskIQ task enqueueing
# ---------------------------------------------------------------------------


class _FakeEnqueuedTask:
    """Fake object returned by ``task.kiq()`` carrying a ``task_id``."""

    def __init__(self, task_id: str = "fake-task-id") -> None:
        self.task_id = task_id


class _FakeTaskiqTask:
    """Fake registered TaskIQ task that records its ``kiq()`` arguments."""

    def __init__(self) -> None:
        self.kiq_args: tuple[Any, ...] | None = None
        self.kiq_kwargs: dict[str, Any] | None = None

    async def kiq(self, *args: Any, **kwargs: Any) -> _FakeEnqueuedTask:
        self.kiq_args = args
        self.kiq_kwargs = kwargs
        return _FakeEnqueuedTask()


class _FakeBroker:
    """Fake broker resolving a configurable task by name."""

    def __init__(self, task: _FakeTaskiqTask | None) -> None:
        self._task = task
        self.find_task_calls: list[str] = []

    def find_task(self, name: str) -> _FakeTaskiqTask | None:
        self.find_task_calls.append(name)
        return self._task


class TestEventListenerDispatch:
    async def test_dispatch_enqueues_registered_task(self) -> None:
        """When the mapped task is registered, it is enqueued with the payload."""
        task = _FakeTaskiqTask()
        broker = _FakeBroker(task=task)
        listener = EventListener("redis://test:6379", broker=broker)

        payload = {"aggregate_id": "kb-1", "content": "hello"}
        await listener._dispatch(EventType.KB_ENTRY_UPDATED, payload)

        assert task.kiq_args == (payload,)
        assert broker.find_task_calls  # a lookup happened

    async def test_dispatch_unknown_event_does_not_enqueue(self) -> None:
        """Events without a mapped task name are skipped without error."""
        task = _FakeTaskiqTask()
        broker = _FakeBroker(task=task)
        listener = EventListener("redis://test:6379", broker=broker)

        # Should not raise; no task lookup for unmapped events.
        await listener._dispatch("UNKNOWN_EVENT", {"x": 1})

        assert task.kiq_args is None
        assert broker.find_task_calls == []

    async def test_dispatch_task_not_registered_does_not_raise(self) -> None:
        """A mapped-but-unregistered task logs and continues without raising."""
        broker = _FakeBroker(task=None)
        listener = EventListener("redis://test:6379", broker=broker)

        # KB_ENTRY_UPDATED is mapped to "embed_source"; simulate the task not
        # being registered yet (find_task returns None).
        await listener._dispatch(EventType.KB_ENTRY_UPDATED, {"aggregate_id": "kb-1"})

        # A lookup was attempted (graceful miss).
        assert broker.find_task_calls

    async def test_dispatch_uses_injected_broker(self) -> None:
        """The injected broker is used directly, not a lazily-imported one."""
        task = _FakeTaskiqTask()
        broker = _FakeBroker(task=task)
        listener = EventListener("redis://test:6379", broker=broker)

        assert listener._get_broker() is broker
