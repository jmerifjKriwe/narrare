"""Unit tests for EmbeddingHookManager — embedding lifecycle hooks.

Tests on_entry_created and on_entry_updated behaviour: task dispatch,
content-changed gating, hash comparison, and silent exception handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.embeddings.models import Embedding
from narrare.kb.embedding_hooks import EmbeddingHookManager
from narrare_core.events.types import DomainEvent, EventType

# ---------------------------------------------------------------------------
# Fake dependencies
# ---------------------------------------------------------------------------


@dataclass
class FakeKBEntry:
    """Minimal fake KB entry with id, body, and novel_id attributes.

    Mimics the SQLAlchemy KBEntry shape without requiring a DB session.
    """

    id: object = None
    body: str = ""
    novel_id: object = None

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = uuid4()
        if self.novel_id is None:
            self.novel_id = uuid4()


class FakeEmbeddingRepo:
    """Fake EmbeddingRepositoryProtocol for hash lookups.

    Configurable: returns an embedding with a specific content_hash,
    or None to simulate no existing embedding.

    Only implements get_by_source — other protocol methods are unused
    by EmbeddingHookManager.
    """

    def __init__(self, existing_hash: str | None = None) -> None:
        self._existing_hash = existing_hash
        self.last_source_type: str | None = None
        self.last_source_id: object | None = None

    async def get_by_source(
        self,
        source_type: str,
        source_id: object,
        model: str | None = None,
    ) -> object | None:
        """Return a fake embedding with the configured hash, or None."""
        self.last_source_type = source_type
        self.last_source_id = source_id
        if self._existing_hash is None:
            return None
        embedding = MagicMock(spec=Embedding)
        embedding.content_hash = self._existing_hash
        return embedding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hash(content: str) -> str:
    """Compute SHA-256 hash matching compute_content_hash."""
    import hashlib

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# on_entry_created — dispatch on creation
# ---------------------------------------------------------------------------


class TestOnEntryCreated:
    """``on_entry_created`` dispatches embedding task."""

    @pytest.mark.asyncio
    async def test_dispatches_task_with_content_hash(self) -> None:
        """on_entry_created computes hash and dispatches embedding task."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry(body="A brave warrior")

        # Patch _dispatch_task to track calls
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_created(entry)  # type: ignore[arg-type]

        manager._dispatch_task.assert_awaited_once()
        call_args = manager._dispatch_task.call_args
        assert call_args[0][0] == entry.id  # source_id
        expected_hash = _make_hash("A brave warrior")
        assert call_args[0][1] == expected_hash  # content_hash
        assert call_args[1]["trigger"] == "create"

    @pytest.mark.asyncio
    async def test_handles_empty_body(self) -> None:
        """on_entry_created handles empty body string."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry(body="")
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_created(entry)  # type: ignore[arg-type]

        manager._dispatch_task.assert_awaited_once()
        expected_hash = _make_hash("")
        assert manager._dispatch_task.call_args[0][1] == expected_hash

    @pytest.mark.asyncio
    async def test_handles_none_body(self) -> None:
        """on_entry_created treats None body as empty string."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry()
        entry.body = None  # type: ignore[assignment]
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_created(entry)  # type: ignore[arg-type]

        manager._dispatch_task.assert_awaited_once()
        expected_hash = _make_hash("")
        assert manager._dispatch_task.call_args[0][1] == expected_hash

    @pytest.mark.asyncio
    async def test_exception_caught_silently(self) -> None:
        """on_entry_created catches exceptions without re-raising (RULE-11)."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry(body="content")

        # Make compute_content_hash raise
        with patch(
            "narrare.kb.embedding_hooks.compute_content_hash",
            side_effect=RuntimeError("hash failed"),
        ):
            # Should NOT raise
            await manager.on_entry_created(entry)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# on_entry_updated — content-changed gating
# ---------------------------------------------------------------------------


class TestOnEntryUpdated:
    """``on_entry_updated`` dispatches only when content changed."""

    @pytest.mark.asyncio
    async def test_skips_when_content_not_changed(self) -> None:
        """on_entry_updated returns immediately when content_changed=False."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry(body="original")
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_updated(entry, content_changed=False)  # type: ignore[arg-type]

        manager._dispatch_task.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dispatches_when_content_changed_no_repo(self) -> None:
        """on_entry_updated dispatches when content_changed=True and no repo."""
        manager = EmbeddingHookManager(embedding_repo=None)
        entry = FakeKBEntry(body="updated content")
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_updated(entry, content_changed=True)  # type: ignore[arg-type]

        manager._dispatch_task.assert_awaited_once()
        assert manager._dispatch_task.call_args[1]["trigger"] == "update"

    @pytest.mark.asyncio
    async def test_dispatches_when_repo_returns_none(self) -> None:
        """on_entry_updated dispatches when repo has no existing embedding."""
        repo = FakeEmbeddingRepo(existing_hash=None)
        manager = EmbeddingHookManager(embedding_repo=repo)  # type: ignore[arg-type]
        entry = FakeKBEntry(body="new content")
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_updated(entry, content_changed=True)  # type: ignore[arg-type]

        manager._dispatch_task.assert_awaited_once()
        assert repo.last_source_type == "kb_entry"
        assert repo.last_source_id == entry.id

    @pytest.mark.asyncio
    async def test_skips_when_hash_matches_existing(self) -> None:
        """on_entry_updated skips dispatch when new hash matches stored hash."""
        content = "unchanged content"
        content_hash = _make_hash(content)
        repo = FakeEmbeddingRepo(existing_hash=content_hash)
        manager = EmbeddingHookManager(embedding_repo=repo)  # type: ignore[arg-type]
        entry = FakeKBEntry(body=content)
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_updated(entry, content_changed=True)  # type: ignore[arg-type]

        manager._dispatch_task.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dispatches_when_hash_differs(self) -> None:
        """on_entry_updated dispatches when new hash differs from stored."""
        repo = FakeEmbeddingRepo(existing_hash="old_hash_value")
        manager = EmbeddingHookManager(embedding_repo=repo)  # type: ignore[arg-type]
        entry = FakeKBEntry(body="modified content")
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_updated(entry, content_changed=True)  # type: ignore[arg-type]

        manager._dispatch_task.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exception_caught_silently(self) -> None:
        """on_entry_updated catches exceptions without re-raising (RULE-11)."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry(body="content")

        with patch(
            "narrare.kb.embedding_hooks.compute_content_hash",
            side_effect=RuntimeError("hash failed"),
        ):
            await manager.on_entry_updated(entry, content_changed=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _publish_wiki_sync_event — wiki sync event publishing
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


class TestWikiSyncEventPublishing:
    """``wiki.sync.requested`` events are published on content changes."""

    @pytest.mark.asyncio
    async def test_on_entry_created_publishes_event(self) -> None:
        """on_entry_created publishes wiki.sync.requested with entity+novel IDs."""
        event_bus = FakeEventBus()
        manager = EmbeddingHookManager(event_bus=event_bus)  # type: ignore[arg-type]
        manager._dispatch_task = AsyncMock()
        novel_id = uuid4()
        entry = FakeKBEntry(body="New character", novel_id=novel_id)

        await manager.on_entry_created(entry)  # type: ignore[arg-type]

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
        manager = EmbeddingHookManager(event_bus=event_bus)  # type: ignore[arg-type]
        manager._dispatch_task = AsyncMock()
        entry = FakeKBEntry(body="Updated content")

        await manager.on_entry_updated(entry, content_changed=True)  # type: ignore[arg-type]

        assert len(event_bus.events) == 1
        assert event_bus.events[0].event_type == EventType.WIKI_SYNC_REQUESTED
        assert event_bus.events[0].payload["entity_id"] == str(entry.id)

    @pytest.mark.asyncio
    async def test_on_entry_updated_without_change_skips_event(self) -> None:
        """on_entry_updated does NOT publish event when content unchanged."""
        event_bus = FakeEventBus()
        manager = EmbeddingHookManager(event_bus=event_bus)  # type: ignore[arg-type]
        manager._dispatch_task = AsyncMock()
        entry = FakeKBEntry(body="Same content")

        await manager.on_entry_updated(entry, content_changed=False)  # type: ignore[arg-type]

        assert len(event_bus.events) == 0

    @pytest.mark.asyncio
    async def test_publish_failure_does_not_raise(self) -> None:
        """When event bus publish fails, error is caught (RULE-11)."""
        event_bus = FakeEventBus()
        event_bus.set_fail(fail=True)
        manager = EmbeddingHookManager(event_bus=event_bus)  # type: ignore[arg-type]
        manager._dispatch_task = AsyncMock()
        entry = FakeKBEntry(body="Content")

        # Should NOT raise — failure is logged and swallowed
        await manager.on_entry_created(entry)  # type: ignore[arg-type]

        # The embedding task was still dispatched despite publish failure
        manager._dispatch_task.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_event_bus_configured_skips_event(self) -> None:
        """When no event_bus is provided, no event is published (graceful)."""
        manager = EmbeddingHookManager()
        manager._dispatch_task = AsyncMock()
        entry = FakeKBEntry(body="Content")

        await manager.on_entry_created(entry)  # type: ignore[arg-type]

        # No event_bus → no event published, but dispatch_task still called
        manager._dispatch_task.assert_awaited_once()


# ---------------------------------------------------------------------------
# _dispatch_task — logging task dispatch
# ---------------------------------------------------------------------------


class TestDispatchTask:
    """``_dispatch_task`` logs the embedding task details."""

    @pytest.mark.asyncio
    async def test_dispatch_task_succeeds(self) -> None:
        """_dispatch_task completes without error (currently logs only)."""
        manager = EmbeddingHookManager()
        source_id = uuid4()
        content_hash = "abc123"

        # Should not raise
        await manager._dispatch_task(source_id, content_hash, trigger="create")
