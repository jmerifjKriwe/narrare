"""Event system for decoupled module communication.

This package defines domain events and the event bus protocol.
Events are purely in-process within core; the API layer's Redis/TaskIQ
adapters were removed per ADR-080.
"""

from narrare_core.events.bus import EventBus, NullEventBus
from narrare_core.events.types import DomainEvent, EventType

__all__ = ["DomainEvent", "EventBus", "EventType", "NullEventBus"]
