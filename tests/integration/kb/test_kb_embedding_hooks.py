"""Integration tests for KB embedding hooks.

Verifies that KB entry create/update triggers embedding task dispatch
via the EmbeddingHookManager, and that the hooks are non-blocking.

Uses the shared ``db_session`` fixture from the integration conftest.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from narrare.kb.embedding_hooks import EmbeddingHookManager
from narrare.kb.models import KBEntry
from narrare.kb.repository import KBRepository
from narrare.kb.schemas import KBEntryCreate, KBEntryUpdate
from narrare.kb.service import KBService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_novel(
    db_session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a user and novel, return (novel_id, user_id)."""
    import sqlalchemy

    user_id = uuid.uuid4()
    novel_id = uuid.uuid4()

    # Create user first (novels has FK to users)
    await db_session.execute(
        sqlalchemy.text(
            "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
            "VALUES (:id, :email, 'fake_hash', now(), now())"
        ),
        {"id": str(user_id), "email": f"test-{user_id.hex[:8]}@example.com"},
    )

    await db_session.execute(
        sqlalchemy.text(
            "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
            "VALUES (:id, :user_id, 'Test Novel', now(), now())"
        ),
        {"id": str(novel_id), "user_id": str(user_id)},
    )
    await db_session.flush()
    return novel_id, user_id


async def _seed_entry(
    db_session: AsyncSession,
    novel_id: uuid.UUID,
    *,
    body: str = "Test content",
    name: str = "Test Entry",
) -> KBEntry:
    """Persist a KB entry and return it."""
    entry = KBEntry(
        novel_id=novel_id,
        entity_type="character",
        name=name,
        slug=name.lower().replace(" ", "-"),
        status="draft",
        body=body,
    )
    repo = KBRepository(db_session)
    return await repo.create(entry)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestKBEntryCreateTriggersEmbedding:
    """kb_entry create triggers embedding task."""

    async def test_create_queues_embedding_task(self, db_session: AsyncSession) -> None:
        """When a KB entry is created, the embedding hook dispatches."""
        novel_id, user_id = await _seed_novel(db_session)

        hook_manager = EmbeddingHookManager()
        hook_manager._dispatch_task = AsyncMock()  # type: ignore[assignment]

        service = KBService(
            repo=KBRepository(db_session),
            novel_repo=None,
            embedding_hooks=hook_manager,
        )

        data = KBEntryCreate(
            entity_type="character",
            name="Forest Spirit",
            body="A mysterious guardian of the ancient woods.",
        )

        entry = await service.create(novel_id, user_id, data)

        hook_manager._dispatch_task.assert_called_once()
        call_args = hook_manager._dispatch_task.call_args
        assert call_args[0][0] == entry.id
        assert call_args[1]["trigger"] == "create"

    async def test_create_forwards_body_content(self, db_session: AsyncSession) -> None:
        """When a KB entry is created, its body is forwarded as content."""
        novel_id, user_id = await _seed_novel(db_session)

        hook_manager = EmbeddingHookManager()
        hook_manager._dispatch_task = AsyncMock()  # type: ignore[assignment]

        service = KBService(
            repo=KBRepository(db_session),
            novel_repo=None,
            embedding_hooks=hook_manager,
        )

        body = "A mysterious guardian of the ancient woods."

        data = KBEntryCreate(
            entity_type="character",
            name="Forest Spirit",
            body=body,
        )

        await service.create(novel_id, user_id, data)

        call_args = hook_manager._dispatch_task.call_args
        assert call_args[0][1] == body  # content forwarded for embedding


class TestKBEntryUpdateTriggersReembedding:
    """kb_entry update with changed content triggers re-embedding."""

    async def test_update_with_changed_content_queues_embedding(
        self, db_session: AsyncSession
    ) -> None:
        """When content changes, embedding hook is called."""
        novel_id, user_id = await _seed_novel(db_session)
        entry = await _seed_entry(db_session, novel_id)

        hook_manager = EmbeddingHookManager()
        hook_manager._dispatch_task = AsyncMock()  # type: ignore[assignment]

        service = KBService(
            repo=KBRepository(db_session),
            novel_repo=None,
            embedding_hooks=hook_manager,
        )

        data = KBEntryUpdate(body="Updated content about the forest spirit.")
        await service.update(novel_id, entry.id, user_id, data)

        hook_manager._dispatch_task.assert_called_once()
        call_args = hook_manager._dispatch_task.call_args
        assert call_args[1]["trigger"] == "update"

    async def test_update_with_unchanged_content_skips_embedding(
        self, db_session: AsyncSession
    ) -> None:
        """When only non-content fields change, no embedding is queued."""
        novel_id, user_id = await _seed_novel(db_session)
        entry = await _seed_entry(db_session, novel_id)

        hook_manager = EmbeddingHookManager()
        hook_manager._dispatch_task = AsyncMock()  # type: ignore[assignment]

        service = KBService(
            repo=KBRepository(db_session),
            novel_repo=None,
            embedding_hooks=hook_manager,
        )

        # Update only status (non-content field)
        data = KBEntryUpdate(status="reviewed")
        await service.update(novel_id, entry.id, user_id, data)

        hook_manager._dispatch_task.assert_not_called()


class TestEmbeddingHookNonBlocking:
    """Embedding task queue failure does not block save."""

    async def test_hook_failure_does_not_block_create(self, db_session: AsyncSession) -> None:
        """When task dispatch fails, the entry is still created."""
        novel_id, user_id = await _seed_novel(db_session)

        hook_manager = EmbeddingHookManager()
        hook_manager._dispatch_task = AsyncMock(  # type: ignore[assignment]
            side_effect=RuntimeError("dispatch failed"),
        )

        service = KBService(
            repo=KBRepository(db_session),
            novel_repo=None,
            embedding_hooks=hook_manager,
        )

        data = KBEntryCreate(
            entity_type="character",
            name="Resilient Entry",
            body="Should be saved despite hook failure.",
        )

        entry = await service.create(novel_id, user_id, data)

        assert entry.id is not None
        assert entry.name == "Resilient Entry"

    async def test_hook_failure_does_not_block_update(self, db_session: AsyncSession) -> None:
        """When hash computation fails, entry is still updated."""
        novel_id, user_id = await _seed_novel(db_session)
        entry = await _seed_entry(db_session, novel_id)

        hook_manager = EmbeddingHookManager()

        service = KBService(
            repo=KBRepository(db_session),
            novel_repo=None,
            embedding_hooks=hook_manager,
        )

        with patch(
            "narrare.kb.embedding_hooks.compute_content_hash",
            side_effect=RuntimeError("Hash failed"),
        ):
            data = KBEntryUpdate(body="Updated despite hook failure")
            updated = await service.update(novel_id, entry.id, user_id, data)

        assert updated.body == "Updated despite hook failure"
