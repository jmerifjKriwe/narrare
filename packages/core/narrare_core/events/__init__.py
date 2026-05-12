"""Event system for decoupled module communication.

This package defines domain events and the event bus protocol.
Infrastructure implementations (Redis, TaskIQ) live in the API layer.
"""

from narrare_core.events.bus import EventBus, NullEventBus
from narrare_core.events.types import DomainEvent, EventType

__all__ = ["DomainEvent", "EventBus", "EventType", "NullEventBus"]
