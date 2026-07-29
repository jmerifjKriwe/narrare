"""Unit tests for EmbeddingHookManager wiki sync event publishing.

Extracted from ``test_embedding_hooks.py`` to stay under RULE-04 file-size
limits. Tests ``wiki.sync.requested`` event publishing, including the
Series-Canon guard that skips novel-scoped wiki sync for entries with
``novel_id IS NULL``.

Embeddings are entry-scoped and always dispatched; wiki sync is
novel-scoped, so Series-Canon entries (``novel_id IS NULL``) must not
trigger it. Series-scoped wiki sync is a future concern (Spec 2+).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from narrare.kb.embedding_hooks import EmbeddingHookManager
from narrare_core.events.types import DomainEvent, EventType

# FakeKBEntry is shared embedding-hook test infrastructure; it lives in the
# sibling module (cross-test import pattern used by test_apply_extraction).
from tests.unit.api.kb.test_embedding_hooks import FakeKBEntry

if TYPE_CHECKING:
    from narrare.kb.models import KBEntry
    from narrare_core.events.bus import EventBus


# ---------------------------------------------------------------------------
# Fake EventBus
# ---------------------------------------------------------------------------


class FakeEventBus:
    """Fake EventBus that records published events for assertion."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []
        self.should_fail = False

    def set_fail(self, *, fail: bool = True) -> None:
        """Make publish raise a RuntimeError to simulate failure."""
        self.should_fail = fail

    async def publish(self, event: DomainEvent) -> None:
        """Record the event or raise if failure mode is active."""
        if self.should_fail:
            raise RuntimeError("Simulated event bus failure")
        self.events.append(event)

    async def subscribe(self, event_type: str, handler: object) -> None:
        """No-op subscribe."""


# ---------------------------------------------------------------------------
# _publish_wiki_sync_event — wiki sync event publishing
# ---------------------------------------------------------------------------


class TestWikiSyncEventPublishing:
    """``wiki.sync.requested`` events are published on content changes."""

    @pytest.mark.asyncio
    async def test_on_entry_created_publishes_event(self) -> None:
        """on_entry_created publishes wiki.sync.requested with entity+novel IDs."""
        event_bus = FakeEventBus()
        manager = EmbeddingHookManager(event_bus=cast("EventBus", event_bus))
        manager._dispatch_task = AsyncMock()
        novel_id = uuid4()
        entry = FakeKBEntry(body="New character", novel_id=novel_id)

        await manager.on_entry_created(cast("KBEntry", entry))

        assert len(event_bus.events) == 1
        event = event_bus.events[0]
        assert event.event_type == EventType.WIKI_SYNC_REQUESTED
        assert event.aggregate_id == entry.id
        assert event.payload == {
            "entity_id": str(entry.id),
            "novel_id": str(novel_id),
        }

    @pytest.mark.asyncio
    async def test_on_entry_updated_with_change_publishes_event(self) -> None:
        """on_entry_updated publishes wiki.sync.requested when content changed."""
        event_bus = FakeEventBus()
        manager = EmbeddingHookManager(event_bus=cast("EventBus", event_bus))
        manager._dispatch_task = AsyncMock()
        entry = FakeKBEntry(body="Updated content")

        await manager.on_entry_updated(cast("KBEntry", entry), content_changed=True)

        assert len(event_bus.events) == 1
        assert event_bus.events[0].event_type == EventType.WIKI_SYNC_REQUESTED
        assert event_bus.events[0].payload["entity_id"] == str(entry.id)

    @pytest.mark.asyncio
    async def test_on_entry_updated_without_change_skips_event(self) -> None:
        """on_entry_updated does NOT publish event when content unchanged."""
        event_bus = FakeEventBus()
        manager = EmbeddingHookManager(event_bus=cast("EventBus", event_bus))
        manager._dispatch_task = AsyncMock()
        entry = FakeKBEntry(body="Same content")

        await manager.on_entry_updated(cast("KBEntry", entry), content_changed=False)

        assert len(event_bus.events) == 0

    @pytest.mark.asyncio
    async def test_publish_failure_does_not_raise(self) -> None:
        """When event bus publish fails, error is caught (RULE-11)."""
        event_bus = FakeEventBus()
        event_bus.set_fail(fail=True)
        manager = EmbeddingHookManager(event_bus=cast("EventBus", event_bus))
        manager._dispatch_task = AsyncMock()
        entry = FakeKBEntry(body="Content")

        # Should NOT raise — failure is logged and swallowed
        await manager.on_entry_created(cast("KBEntry", entry))

        # The embedding task was still dispatched despite publish failure
        manager._dispatch_task.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_event_bus_configured_skips_event(self) -> None:
        """When no event_bus is provided, no event is published (graceful)."""
        manager = EmbeddingHookManager()
        manager._dispatch_task = AsyncMock()
        entry = FakeKBEntry(body="Content")

        await manager.on_entry_created(cast("KBEntry", entry))

        # No event_bus → no event published, but dispatch_task still called
        manager._dispatch_task.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_canon_entry_created_skips_wiki_sync(self) -> None:
        """Canon entry (novel_id IS NULL) dispatches embeddings but no wiki sync.

        Wiki sync is novel-scoped; Series-Canon entries belong to a series,
        not a novel, so the event must not be published. Embeddings are
        entry-scoped and must still be dispatched.
        """
        event_bus = FakeEventBus()
        manager = EmbeddingHookManager(event_bus=cast("EventBus", event_bus))
        manager._dispatch_task = AsyncMock()
        entry = FakeKBEntry(body="Canon character")
        cast("Any", entry).novel_id = None  # Series-Canon entry

        await manager.on_entry_created(cast("KBEntry", entry))

        # Embeddings (entry-scoped) still dispatched for Canon entries.
        manager._dispatch_task.assert_awaited_once()
        # Wiki sync (novel-scoped) skipped — no event published.
        assert event_bus.events == []

    @pytest.mark.asyncio
    async def test_canon_entry_updated_skips_wiki_sync(self) -> None:
        """Canon entry update (novel_id IS NULL) dispatches embeddings but no wiki sync."""
        event_bus = FakeEventBus()
        manager = EmbeddingHookManager(event_bus=cast("EventBus", event_bus))
        manager._dispatch_task = AsyncMock()
        entry = FakeKBEntry(body="Canon character, revised")
        cast("Any", entry).novel_id = None  # Series-Canon entry

        await manager.on_entry_updated(cast("KBEntry", entry), content_changed=True)

        # Embeddings (entry-scoped) still dispatched for Canon entries.
        manager._dispatch_task.assert_awaited_once()
        # Wiki sync (novel-scoped) skipped — no event published.
        assert event_bus.events == []
