"""Unit tests for EmbeddingHookManager — embedding lifecycle hooks.

Tests on_entry_created and on_entry_updated behaviour: task dispatch,
content-changed gating, hash comparison, and silent exception handling.
The ADR-080 ``_dispatch_task`` internals live in
``test_embedding_hooks_dispatch.py`` (RULE-04 split).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare.embeddings.models import Embedding
from narrare.kb.embedding_hooks import EmbeddingHookManager

if TYPE_CHECKING:
    from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
    from narrare.kb.models import KBEntry

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
    async def test_dispatches_task_with_content(self) -> None:
        """on_entry_created forwards the entry body as content to dispatch."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry(body="A brave warrior")

        # Patch _dispatch_task to track calls
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_created(cast("KBEntry", entry))

        manager._dispatch_task.assert_awaited_once()
        call_args = manager._dispatch_task.call_args
        assert call_args[0][0] == entry.id  # source_id
        assert call_args[0][1] == "A brave warrior"  # content (body)
        assert call_args[1]["trigger"] == "create"

    @pytest.mark.asyncio
    async def test_handles_empty_body(self) -> None:
        """on_entry_created forwards empty body as empty content."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry(body="")
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_created(cast("KBEntry", entry))

        manager._dispatch_task.assert_awaited_once()
        assert manager._dispatch_task.call_args[0][1] == ""

    @pytest.mark.asyncio
    async def test_handles_none_body(self) -> None:
        """on_entry_created treats None body as empty content."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry()
        cast("Any", entry).body = None
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_created(cast("KBEntry", entry))

        manager._dispatch_task.assert_awaited_once()
        assert manager._dispatch_task.call_args[0][1] == ""

    @pytest.mark.asyncio
    async def test_exception_caught_silently(self) -> None:
        """on_entry_created catches exceptions without re-raising (RULE-11)."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry(body="content")

        # Make _dispatch_task raise to exercise the exception guard.
        manager._dispatch_task = AsyncMock(side_effect=RuntimeError("dispatch failed"))

        # Should NOT raise
        await manager.on_entry_created(cast("KBEntry", entry))


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

        await manager.on_entry_updated(cast("KBEntry", entry), content_changed=False)

        manager._dispatch_task.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dispatches_when_content_changed_no_repo(self) -> None:
        """on_entry_updated dispatches when content_changed=True and no repo."""
        manager = EmbeddingHookManager(embedding_repo=None)
        entry = FakeKBEntry(body="updated content")
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_updated(cast("KBEntry", entry), content_changed=True)

        manager._dispatch_task.assert_awaited_once()
        assert manager._dispatch_task.call_args[1]["trigger"] == "update"

    @pytest.mark.asyncio
    async def test_dispatches_when_repo_returns_none(self) -> None:
        """on_entry_updated dispatches when repo has no existing embedding."""
        repo = FakeEmbeddingRepo(existing_hash=None)
        manager = EmbeddingHookManager(embedding_repo=cast("EmbeddingRepositoryProtocol", repo))
        entry = FakeKBEntry(body="new content")
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_updated(cast("KBEntry", entry), content_changed=True)

        manager._dispatch_task.assert_awaited_once()
        assert repo.last_source_type == "kb_entry"
        assert repo.last_source_id == entry.id

    @pytest.mark.asyncio
    async def test_skips_when_hash_matches_existing(self) -> None:
        """on_entry_updated skips dispatch when new hash matches stored hash."""
        content = "unchanged content"
        content_hash = _make_hash(content)
        repo = FakeEmbeddingRepo(existing_hash=content_hash)
        manager = EmbeddingHookManager(embedding_repo=cast("EmbeddingRepositoryProtocol", repo))
        entry = FakeKBEntry(body=content)
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_updated(cast("KBEntry", entry), content_changed=True)

        manager._dispatch_task.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dispatches_when_hash_differs(self) -> None:
        """on_entry_updated dispatches when new hash differs from stored."""
        repo = FakeEmbeddingRepo(existing_hash="old_hash_value")
        manager = EmbeddingHookManager(embedding_repo=cast("EmbeddingRepositoryProtocol", repo))
        entry = FakeKBEntry(body="modified content")
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_updated(cast("KBEntry", entry), content_changed=True)

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
            await manager.on_entry_updated(cast("KBEntry", entry), content_changed=True)


# ---------------------------------------------------------------------------
# No wiki-sync coupling — dead path removed (PR #157 finding #4)
# ---------------------------------------------------------------------------


class TestNoWikiSyncCoupling:
    """The hook has no ``wiki.sync.requested`` event-bus path.

    Regression guard against silent resurrection of the dead wiki-sync
    publish path: the constructor must not accept an ``event_bus`` and
    instances must not carry a ``_event_bus`` attribute. Embedding dispatch
    is the hook's only side effect.
    """

    def test_constructor_has_no_event_bus_parameter(self) -> None:
        """EmbeddingHookManager.__init__ no longer accepts ``event_bus``."""
        import inspect

        params = inspect.signature(EmbeddingHookManager.__init__).parameters
        assert "event_bus" not in params

    def test_instance_has_no_event_bus_attribute(self) -> None:
        """Instances do not carry a ``_event_bus`` attribute."""
        manager = EmbeddingHookManager()
        assert not hasattr(manager, "_event_bus")

    @pytest.mark.asyncio
    async def test_on_entry_created_dispatches_without_event_bus(self) -> None:
        """on_entry_created dispatches embeddings with zero bus coupling."""
        manager = EmbeddingHookManager()
        entry = FakeKBEntry(body="content")
        manager._dispatch_task = AsyncMock()

        await manager.on_entry_created(cast("KBEntry", entry))

        manager._dispatch_task.assert_awaited_once()
