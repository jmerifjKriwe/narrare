"""SQLAlchemy-backed conversation store for production use.

Implements the abstract ``ConversationStore`` from core using
SQLAlchemy async ORM for PostgreSQL persistence.

Ownership contract (IDOR hardening): history read/clear/project lookup
filter by ``user_id``. Foreign and unknown conversations raise
``NotFoundError`` (→ HTTP 404 via the global handler) — callers cannot
probe for other users' conversations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

from sqlalchemy import delete, select

from narrare_core.chat.contracts import ChatConversation, ChatMessage
from narrare_core.chat.conversation_store import ConversationStore
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyConversationStore(ConversationStore):
    """PostgreSQL-backed conversation store.

    Persists conversations and messages to the database via SQLAlchemy.
    Implements the ``ConversationStore`` ABC defined in core.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> ChatConversation:
        """Return owned conversation metadata; NotFoundError otherwise.

        Single ownership primitive for this store (pre-write gate for
        ``ChatService.ask()`` and read/clear gate for the history API):
        the row lookup filters by ``id + user_id`` so foreign and unknown
        conversations are indistinguishable.
        """
        from narrare.chat.models import ChatConversation as ChatConversationModel

        result = await self._session.execute(
            select(ChatConversationModel).where(
                ChatConversationModel.id == conversation_id,
                ChatConversationModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("ChatConversation", identifier=str(conversation_id))
        return ChatConversation(
            id=row.id,
            project_id=row.project_id,
            user_id=row.user_id,
            title=row.title or "",
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
        )

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        *,
        tokens: int | None = None,
    ) -> ChatMessage:
        """Add a message to a conversation and persist it."""
        from narrare.chat.models import ChatMessage as ChatMessageModel

        msg = ChatMessageModel(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tokens=tokens,
        )
        self._session.add(msg)
        await self._session.commit()

        return ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=datetime.now(UTC).isoformat(),
        )

    async def get_history(
        self,
        conversation_id: UUID,
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        """Get the message history for a conversation owned by ``user_id``."""
        from narrare.chat.models import ChatMessage as ChatMessageModel

        await self.get_conversation(conversation_id, user_id)

        result = await self._session.execute(
            select(ChatMessageModel)
            .where(ChatMessageModel.conversation_id == conversation_id)
            .order_by(ChatMessageModel.created_at)
            .limit(limit)
        )
        messages = result.scalars().all()

        return [
            ChatMessage(
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at.isoformat() if m.created_at else "",
            )
            for m in messages
        ]

    async def create_conversation(
        self,
        project_id: UUID | None,
        user_id: UUID,
        first_message: str,
    ) -> UUID:
        """Create a new conversation and add the first message.

        ``project_id`` may be ``None`` for project-less conversations
        (NOTES-001 §6b — the column is nullable since migration 0042).
        """
        from narrare.chat.models import ChatConversation as ChatConversationModel

        conv = ChatConversationModel(
            project_id=project_id,
            user_id=user_id,
        )
        self._session.add(conv)
        await self._session.flush()

        await self.add_message(conv.id, "user", first_message)
        return conv.id

    async def get_conversation_project_id(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> UUID | None:
        """Return the project_id for an owned conversation, or None.

        ``None`` strictly means project-less (NOTES-001 §6b) — unknown or
        foreign conversations raise ``NotFoundError`` instead. Selecting
        ``(id, project_id)`` keeps a project-less row distinguishable from
        no row at all.
        """
        from narrare.chat.models import ChatConversation as ChatConversationModel

        result = await self._session.execute(
            select(ChatConversationModel.id, ChatConversationModel.project_id).where(
                ChatConversationModel.id == conversation_id,
                ChatConversationModel.user_id == user_id,
            )
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError("ChatConversation", identifier=str(conversation_id))
        return row.project_id

    async def clear_history(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> None:
        """Delete all messages in a conversation owned by ``user_id``."""
        from narrare.chat.models import ChatMessage as ChatMessageModel

        await self.get_conversation(conversation_id, user_id)

        await self._session.execute(
            delete(ChatMessageModel).where(ChatMessageModel.conversation_id == conversation_id)
        )
        await self._session.commit()
