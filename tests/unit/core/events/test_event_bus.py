"""Tests for events/bus.py — EventBus protocol and NullEventBus.

Covers:
1. NullEventBus.publish() is no-op
2. NullEventBus.subscribe() is no-op
3. NullEventBus satisfies EventBus protocol (isinstance check)
4. EventBus is runtime-checkable
"""

from __future__ import annotations

import uuid

import pytest

from narrare_core.events.bus import EventBus, NullEventBus
from narrare_core.events.types import DomainEvent, EventType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(**overrides: object) -> DomainEvent:
    """Build a DomainEvent with sensible defaults."""
    defaults = {
        "event_type": EventType.CHAPTER_CREATED,
        "aggregate_id": uuid.uuid4(),
    }
    defaults.update(overrides)  # type: ignore[arg-type]
    return DomainEvent(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# NullEventBus — publish
# ---------------------------------------------------------------------------


class TestNullEventBusPublish:
    """NullEventBus.publish() absorbs all calls silently."""

    @pytest.mark.asyncio
    async def test_publish_does_not_raise(self) -> None:
        bus = NullEventBus()
        event = _make_event()
        # Should silently succeed
        await bus.publish(event)

    @pytest.mark.asyncio
    async def test_publish_with_empty_payload(self) -> None:
        bus = NullEventBus()
        event = _make_event(payload={})
        await bus.publish(event)

    @pytest.mark.asyncio
    async def test_publish_with_payload_data(self) -> None:
        bus = NullEventBus()
        event = _make_event(
            payload={"title": "Chapter 1", "word_count": 500},
        )
        await bus.publish(event)


# ---------------------------------------------------------------------------
# NullEventBus — subscribe
# ---------------------------------------------------------------------------


class TestNullEventBusSubscribe:
    """NullEventBus.subscribe() absorbs all calls silently."""

    @pytest.mark.asyncio
    async def test_subscribe_does_not_raise(self) -> None:
        bus = NullEventBus()

        async def handler(event: DomainEvent) -> None:
            pass

        await bus.subscribe("chapter.created", handler)

    @pytest.mark.asyncio
    async def test_subscribe_with_non_async_handler(self) -> None:
        bus = NullEventBus()
        # Accepts any object as handler — no signature check
        await bus.subscribe("chapter.deleted", None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestNullEventBusProtocolConformance:
    """NullEventBus satisfies the EventBus protocol."""

    def test_isinstance_event_bus(self) -> None:
        bus = NullEventBus()
        assert isinstance(bus, EventBus)

    def test_event_bus_is_runtime_checkable(self) -> None:
        """EventBus is decorated with @runtime_checkable."""
        # If this passes without error, the protocol is runtime_checkable
        assert isinstance(NullEventBus(), EventBus)


class TestCustomEventBusImplementation:
    """A custom class implementing EventBus satisfies isinstance check."""

    def test_custom_impl_is_event_bus(self) -> None:
        class MyBus:
            async def publish(self, event: DomainEvent) -> None:
                pass

            async def subscribe(self, event_type: str, handler: object) -> None:
                pass

        assert isinstance(MyBus(), EventBus)

    def test_incomplete_impl_is_not_event_bus(self) -> None:
        """A class missing methods should not satisfy EventBus."""

        class IncompleteBus:
            async def publish(self, event: DomainEvent) -> None:
                pass

        # Missing subscribe — should NOT satisfy the protocol
        assert not isinstance(IncompleteBus(), EventBus)
