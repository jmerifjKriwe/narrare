"""Integration tests for the SQLAlchemy conversation store (NOTES-001 §6b).

The concrete store's project-less path (``create_conversation(None, ...)``)
is production-reachable since chat accepts requests without a project —
these tests pin it against a real PostgreSQL schema (migration 0042 made
``chat_conversations.project_id`` nullable).

Also pins ownership scoping (IDOR hardening): history read/clear/project
resolution are filtered by ``user_id``; foreign and unknown conversations
are indistinguishable (both raise NotFoundError → HTTP 404).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


async def _make_user(db_session: AsyncSession) -> UUID:
    """Insert a user row and return its id (FK target for conversations)."""
    from datetime import UTC, datetime
    from uuid import uuid4

    from narrare.auth.models import User

    user = User(
        id=uuid4(),
        email=f"chat-store-{uuid4().hex[:12]}@example.com",
        hashed_password="test-hash-only",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.flush()
    return user.id


class TestSQLAlchemyConversationStoreProjectless:
    """create_conversation(None, ...) persists a project-less conversation."""

    async def test_create_conversation_with_none_project_persists_null(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore

        store = SQLAlchemyConversationStore(db_session)
        user_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, user_id, "Craft question")

        stored_project = await store.get_conversation_project_id(conv_id, user_id)
        assert stored_project is None

    async def test_create_conversation_with_none_project_persists_first_message(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore

        store = SQLAlchemyConversationStore(db_session)
        user_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, user_id, "First message")

        history = await store.get_history(conv_id, user_id)
        assert len(history) == 1
        assert history[0].role == "user"
        assert history[0].content == "First message"


class TestSQLAlchemyConversationStoreGetConversation:
    """Scoped conversation resolution — the pre-write ownership gate.

    ``get_conversation`` powers the ownership check in ``ChatService.ask()``
    BEFORE any message row is appended (write-pollution hardening).
    """

    async def test_get_conversation_with_owner_returns_metadata(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore

        store = SQLAlchemyConversationStore(db_session)
        owner_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, owner_id, "Hello")

        conv = await store.get_conversation(conv_id, owner_id)

        assert conv.id == conv_id
        assert conv.project_id is None
        assert conv.user_id == owner_id

    async def test_get_conversation_with_foreign_user_raises_not_found(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore
        from narrare_core.shared.errors import NotFoundError

        store = SQLAlchemyConversationStore(db_session)
        owner_id = await _make_user(db_session)
        attacker_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, owner_id, "Private")

        with pytest.raises(NotFoundError):
            await store.get_conversation(conv_id, attacker_id)

    async def test_get_conversation_with_unknown_conversation_raises_not_found(
        self,
        db_session: AsyncSession,
    ) -> None:
        from uuid import uuid4

        from narrare.chat.conversation_store import SQLAlchemyConversationStore
        from narrare_core.shared.errors import NotFoundError

        store = SQLAlchemyConversationStore(db_session)
        user_id = await _make_user(db_session)

        with pytest.raises(NotFoundError):
            await store.get_conversation(uuid4(), user_id)


class TestSQLAlchemyConversationStoreOwnership:
    """History access is scoped to the conversation's owner (IDOR hardening).

    Foreign and unknown conversations behave identically (NotFoundError →
    HTTP 404 via the global handler) — no existence oracle for other
    users' conversations.
    """

    async def test_get_history_with_owner_returns_messages(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore

        store = SQLAlchemyConversationStore(db_session)
        owner_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, owner_id, "Owner message")

        history = await store.get_history(conv_id, owner_id)

        assert [m.content for m in history] == ["Owner message"]

    async def test_get_history_with_foreign_user_raises_not_found(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore
        from narrare_core.shared.errors import NotFoundError

        store = SQLAlchemyConversationStore(db_session)
        owner_id = await _make_user(db_session)
        attacker_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, owner_id, "Private message")

        with pytest.raises(NotFoundError):
            await store.get_history(conv_id, attacker_id)

    async def test_get_history_with_unknown_conversation_raises_not_found(
        self,
        db_session: AsyncSession,
    ) -> None:
        from uuid import uuid4

        from narrare.chat.conversation_store import SQLAlchemyConversationStore
        from narrare_core.shared.errors import NotFoundError

        store = SQLAlchemyConversationStore(db_session)
        user_id = await _make_user(db_session)

        with pytest.raises(NotFoundError):
            await store.get_history(uuid4(), user_id)

    async def test_clear_history_with_foreign_user_raises_not_found_and_keeps_messages(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore
        from narrare_core.shared.errors import NotFoundError

        store = SQLAlchemyConversationStore(db_session)
        owner_id = await _make_user(db_session)
        attacker_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, owner_id, "Survives attack")

        with pytest.raises(NotFoundError):
            await store.clear_history(conv_id, attacker_id)

        history = await store.get_history(conv_id, owner_id)
        assert [m.content for m in history] == ["Survives attack"]

    async def test_clear_history_with_owner_deletes_messages(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore

        store = SQLAlchemyConversationStore(db_session)
        owner_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, owner_id, "Deleted soon")

        await store.clear_history(conv_id, owner_id)

        assert await store.get_history(conv_id, owner_id) == []

    async def test_get_conversation_project_id_with_foreign_user_raises_not_found(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore
        from narrare_core.shared.errors import NotFoundError

        store = SQLAlchemyConversationStore(db_session)
        owner_id = await _make_user(db_session)
        attacker_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, owner_id, "Hello")

        with pytest.raises(NotFoundError):
            await store.get_conversation_project_id(conv_id, attacker_id)

    async def test_get_conversation_project_id_with_owner_returns_none_for_projectless(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore

        store = SQLAlchemyConversationStore(db_session)
        owner_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, owner_id, "Hello")

        stored = await store.get_conversation_project_id(conv_id, owner_id)

        # Project-less (NOTES-001 §6b): None means exactly that — the
        # conversation exists and is owned, it just has no project.
        assert stored is None
