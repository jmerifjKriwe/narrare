"""Conversation store — abstract + in-memory implementation.

Production implementations live in the backend layer (SQLAlchemy).
The InMemoryConversationStore is for testing and local development.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID, uuid4

from narrare_core.chat.contracts import ChatMessage


class ConversationStore(ABC):
    """Abstract store for chat conversation history.

    Implementations:
    - InMemoryConversationStore: Testing / local dev (this file)
    - SQLAlchemyConversationStore: Production (apps/api layer)
    """

    @abstractmethod
    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        *,
        tokens: int | None = None,
    ) -> ChatMessage: ...

    @abstractmethod
    async def get_history(
        self,
        conversation_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]: ...

    @abstractmethod
    async def create_conversation(
        self,
        project_id: UUID | None,
        user_id: UUID,
        first_message: str,
    ) -> UUID:
        """Create a new conversation and store its first message.

        ``project_id`` may be ``None`` for project-less conversations (NOTES-001 §6b).
        """
        ...

    @abstractmethod
    async def get_conversation_project_id(
        self,
        conversation_id: UUID,
    ) -> UUID | None:
        """Return the project_id for a conversation, or None if not found.

        Args:
            conversation_id: The conversation to look up.

        Returns:
            The project UUID associated with the conversation, or None
            if the conversation does not exist.
        """
        ...

    @abstractmethod
    async def clear_history(
        self,
        conversation_id: UUID,
    ) -> None: ...


class InMemoryConversationStore(ConversationStore):
    """In-memory store — no persistence across restarts.

    Useful for testing and local development without PostgreSQL.
    """

    def __init__(self, *, max_messages: int = 50) -> None:
        self._max_messages = max_messages
        self._messages: dict[UUID, list[ChatMessage]] = {}
        self._conversations: dict[UUID, dict[str, object]] = {}

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        *,
        tokens: int | None = None,
    ) -> ChatMessage:
        from datetime import datetime, timezone

        msg = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc).isoformat(),  # noqa: UP017 — datetime is the class, not module
        )
        self._messages.setdefault(conversation_id, []).append(msg)
        # Auto-trim if over limit
        if len(self._messages[conversation_id]) > self._max_messages:
            self._messages[conversation_id] = self._messages[conversation_id][-self._max_messages :]
        return msg

    async def get_history(
        self,
        conversation_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        history = self._messages.get(conversation_id, [])
        return history[-limit:]

    async def create_conversation(
        self,
        project_id: UUID | None,
        user_id: UUID,
        first_message: str,
    ) -> UUID:
        conv_id = uuid4()
        self._conversations[conv_id] = {
            "project_id": project_id,
            "user_id": user_id,
        }
        await self.add_message(conv_id, "user", first_message)
        return conv_id

    async def get_conversation_project_id(
        self,
        conversation_id: UUID,
    ) -> UUID | None:
        """Return the project_id for a conversation, or None if not found."""
        conv = self._conversations.get(conversation_id)
        if conv is None:
            return None
        project_id = conv.get("project_id")
        return project_id if isinstance(project_id, UUID) else None

    async def clear_history(
        self,
        conversation_id: UUID,
    ) -> None:
        self._messages.pop(conversation_id, None)
        self._conversations.pop(conversation_id, None)
