"""SQLAlchemy-backed conversation store for production use.

Implements the abstract ``ConversationStore`` from core using
SQLAlchemy async ORM for PostgreSQL persistence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

from sqlalchemy import delete, select

from narrare_core.chat.contracts import ChatMessage
from narrare_core.chat.conversation_store import ConversationStore

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyConversationStore(ConversationStore):
    """PostgreSQL-backed conversation store.

    Persists conversations and messages to the database via SQLAlchemy.
    Implements the ``ConversationStore`` ABC defined in core.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        """Get the message history for a conversation."""
        from narrare.chat.models import ChatMessage as ChatMessageModel

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
        project_id: UUID,
        user_id: UUID,
        first_message: str,
    ) -> UUID:
        """Create a new conversation and add the first message."""
        from narrare.chat.models import ChatConversation as ChatConversationModel

        conv = ChatConversationModel(
            project_id=project_id,
            user_id=user_id,
        )
        self._session.add(conv)
        await self._session.flush()

        await self.add_message(conv.id, "user", first_message)
        return conv.id

    async def clear_history(
        self,
        conversation_id: UUID,
    ) -> None:
        """Delete all messages in a conversation."""
        from narrare.chat.models import ChatMessage as ChatMessageModel

        await self._session.execute(
            delete(ChatMessageModel).where(ChatMessageModel.conversation_id == conversation_id)
        )
        await self._session.commit()
