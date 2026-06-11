"""Tests for events/types.py — EventType enum and DomainEvent dataclass.

Covers:
1. EventType enum values
2. DomainEvent creation, defaults, immutability
3. DomainEvent serialization
4. Edge cases (UUID generation, timestamps, frozen dataclass)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

import pytest

from narrare_core.events.types import DomainEvent, EventType

# ---------------------------------------------------------------------------
# EventType enum
# ---------------------------------------------------------------------------


class TestEventTypeValues:
    """EventType enum has correct string values."""

    def test_chapter_created(self) -> None:
        assert EventType.CHAPTER_CREATED == "chapter.created"

    def test_chapter_content_updated(self) -> None:
        assert EventType.CHAPTER_CONTENT_UPDATED == "chapter.content.updated"

    def test_chapter_deleted(self) -> None:
        assert EventType.CHAPTER_DELETED == "chapter.deleted"

    def test_chapter_reordered(self) -> None:
        assert EventType.CHAPTER_REORDERED == "chapter.reordered"

    def test_kb_entry_created(self) -> None:
        assert EventType.KB_ENTRY_CREATED == "kb.entry.created"

    def test_kb_entry_updated(self) -> None:
        assert EventType.KB_ENTRY_UPDATED == "kb.entry.updated"

    def test_kb_entry_deleted(self) -> None:
        assert EventType.KB_ENTRY_DELETED == "kb.entry.deleted"

    def test_novel_created(self) -> None:
        assert EventType.NOVEL_CREATED == "novel.created"

    def test_novel_settings_changed(self) -> None:
        assert EventType.NOVEL_SETTINGS_CHANGED == "novel.settings.changed"

    def test_chapter_version_restored(self) -> None:
        assert EventType.CHAPTER_VERSION_RESTORED == "chapter.version.restored"


class TestEventTypeIsStrEnum:
    """EventType is a StrEnum — values are strings."""

    def test_string_comparison(self) -> None:
        assert EventType.CHAPTER_CREATED == "chapter.created"
        assert isinstance(EventType.CHAPTER_CREATED, str)

    def test_iteration(self) -> None:
        all_values = list(EventType)
        assert (
            len(all_values) == 13
        )  # 10 original + CHAPTER_FINALIZED + WIKI_PROMPT_CHANGED + WIKI_SYNC_REQUESTED


# ---------------------------------------------------------------------------
# DomainEvent — creation and defaults
# ---------------------------------------------------------------------------


class TestDomainEventCreation:
    """DomainEvent can be created with minimal args."""

    def test_minimal_creation(self) -> None:
        event = DomainEvent(
            event_type=EventType.CHAPTER_CREATED,
            aggregate_id=uuid.uuid4(),
        )
        assert event.event_type == EventType.CHAPTER_CREATED
        assert isinstance(event.aggregate_id, uuid.UUID)

    def test_event_id_auto_generated(self) -> None:
        event = DomainEvent(
            event_type=EventType.CHAPTER_CREATED,
            aggregate_id=uuid.uuid4(),
        )
        assert isinstance(event.event_id, uuid.UUID)
        assert event.event_id.version == 4

    def test_event_ids_are_unique(self) -> None:
        e1 = DomainEvent(event_type=EventType.CHAPTER_CREATED, aggregate_id=uuid.uuid4())
        e2 = DomainEvent(event_type=EventType.CHAPTER_CREATED, aggregate_id=uuid.uuid4())
        assert e1.event_id != e2.event_id

    def test_timestamp_auto_generated(self) -> None:
        event = DomainEvent(
            event_type=EventType.CHAPTER_CREATED,
            aggregate_id=uuid.uuid4(),
        )
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo is not None

    def test_default_payload_empty(self) -> None:
        event = DomainEvent(
            event_type=EventType.CHAPTER_CREATED,
            aggregate_id=uuid.uuid4(),
        )
        assert event.payload == {}

    def test_default_correlation_id_empty(self) -> None:
        event = DomainEvent(
            event_type=EventType.CHAPTER_CREATED,
            aggregate_id=uuid.uuid4(),
        )
        assert event.correlation_id == ""

    def test_default_user_id_none(self) -> None:
        event = DomainEvent(
            event_type=EventType.CHAPTER_CREATED,
            aggregate_id=uuid.uuid4(),
        )
        assert event.user_id is None


class TestDomainEventWithAllFields:
    """DomainEvent with all fields specified."""

    def test_full_event(self) -> None:
        agg_id = uuid.uuid4()
        user_id = uuid.uuid4()
        event = DomainEvent(
            event_type=EventType.KB_ENTRY_UPDATED,
            aggregate_id=agg_id,
            payload={"field": "name", "old_value": "Alice", "new_value": "Bob"},
            correlation_id="trace-123",
            user_id=user_id,
        )
        assert event.aggregate_id == agg_id
        assert event.payload["field"] == "name"
        assert event.correlation_id == "trace-123"
        assert event.user_id == user_id


# ---------------------------------------------------------------------------
# DomainEvent — immutability (frozen dataclass)
# ---------------------------------------------------------------------------


class TestDomainEventImmutability:
    """DomainEvent is frozen — attribute mutation raises FrozenInstanceError."""

    def test_cannot_mutate_event_type(self) -> None:
        event = DomainEvent(event_type=EventType.CHAPTER_CREATED, aggregate_id=uuid.uuid4())
        with pytest.raises(AttributeError):
            cast("Any", event).event_type = EventType.CHAPTER_DELETED

    def test_cannot_mutate_payload(self) -> None:
        event = DomainEvent(event_type=EventType.CHAPTER_CREATED, aggregate_id=uuid.uuid4())
        with pytest.raises(AttributeError):
            cast("Any", event).payload = {"new": "data"}

    def test_cannot_mutate_aggregate_id(self) -> None:
        event = DomainEvent(event_type=EventType.CHAPTER_CREATED, aggregate_id=uuid.uuid4())
        with pytest.raises(AttributeError):
            cast("Any", event).aggregate_id = uuid.uuid4()
