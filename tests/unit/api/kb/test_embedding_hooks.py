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

# ---------------------------------------------------------------------------
# Fake dependencies
# ---------------------------------------------------------------------------


@dataclass
class FakeKBEntry:
    """Minimal fake KB entry with id and body attributes.

    Mimics the SQLAlchemy KBEntry shape without requiring a DB session.
    """

    id: object = None
    body: str = ""

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = uuid4()


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
