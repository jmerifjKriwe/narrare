"""Domain event types.

Defines all event types and the DomainEvent dataclass used across Narrare.
This module has NO infrastructure dependencies — no Redis, no TaskIQ, no DB.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    """All domain events in Narrare.

    Values follow the pattern ``entity.action`` for easy Redis channel routing.
    """

    # Chapter events
    CHAPTER_CREATED = "chapter.created"
    CHAPTER_CONTENT_UPDATED = "chapter.content.updated"
    CHAPTER_DELETED = "chapter.deleted"
    CHAPTER_REORDERED = "chapter.reordered"

    # KB events
    KB_ENTRY_CREATED = "kb.entry.created"
    KB_ENTRY_UPDATED = "kb.entry.updated"
    KB_ENTRY_DELETED = "kb.entry.deleted"

    # Novel events
    NOVEL_CREATED = "novel.created"
    NOVEL_SETTINGS_CHANGED = "novel.settings.changed"

    # Version events
    CHAPTER_VERSION_RESTORED = "chapter.version.restored"


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """A domain event carrying data about what happened.

    Events are published by services after a state change completes.
    They are **never** the source of truth — the database is.

    Attributes:
        event_type: What kind of event occurred.
        aggregate_id: The primary entity this event is about.
        payload: Arbitrary data relevant to the event.
        event_id: Unique identifier for this event instance.
        timestamp: When the event was created (UTC).
        correlation_id: Optional tracing ID across service boundaries.
        user_id: Optional user who triggered the event.
    """

    event_type: EventType
    aggregate_id: uuid.UUID
    payload: dict[str, Any] = field(default_factory=dict[str, Any])
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str = ""
    user_id: uuid.UUID | None = None
