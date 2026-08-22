"""Integration tests for the SQLAlchemy conversation store (NOTES-001 §6b).

The concrete store's project-less path (``create_conversation(None, ...)``)
is production-reachable since chat accepts requests without a project —
these tests pin it against a real PostgreSQL schema (migration 0042 made
``chat_conversations.project_id`` nullable).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

        stored_project = await store.get_conversation_project_id(conv_id)
        assert stored_project is None

    async def test_create_conversation_with_none_project_persists_first_message(
        self,
        db_session: AsyncSession,
    ) -> None:
        from narrare.chat.conversation_store import SQLAlchemyConversationStore

        store = SQLAlchemyConversationStore(db_session)
        user_id = await _make_user(db_session)

        conv_id = await store.create_conversation(None, user_id, "First message")

        history = await store.get_history(conv_id)
        assert len(history) == 1
        assert history[0].role == "user"
        assert history[0].content == "First message"
