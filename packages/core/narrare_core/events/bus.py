"""Event bus protocol — defines the interface.

This module defines what an event bus looks like so core stays
infrastructure-free (RULE-07: core defines protocol, API implements).
Events are purely in-process; the API layer's Redis Pub/Sub adapter was
removed per ADR-080.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare_core.events.types import DomainEvent


@runtime_checkable
class EventBus(Protocol):
    """Protocol for event bus implementations.

    Implementations must provide ``publish`` and ``subscribe``.
    Core ships ``NullEventBus``; the API layer's Redis-backed version was
    removed per ADR-080.
    """

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribers."""
        ...

    async def subscribe(self, event_type: str, handler: object) -> None:
        """Subscribe a handler to an event type."""
        ...


class NullEventBus:
    """No-op event bus for testing or when events are disabled.

    Implements the EventBus protocol silently — all calls are absorbed.
    """

    async def publish(self, event: DomainEvent) -> None:
        """No-op publish."""
        pass

    async def subscribe(self, event_type: str, handler: object) -> None:
        """No-op subscribe."""
        pass
