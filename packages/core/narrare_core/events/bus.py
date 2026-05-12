"""Event bus protocol — defines the interface.

Actual implementations live in the API layer (Redis Pub/Sub).
This module defines what an event bus looks like so core stays
infrastructure-free (RULE-07: core defines protocol, API implements).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare_core.events.types import DomainEvent


@runtime_checkable
class EventBus(Protocol):
    """Protocol for event bus implementations.

    Implementations must provide ``publish`` and ``subscribe``.
    The API layer provides a Redis-backed version; tests use NullEventBus.
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
