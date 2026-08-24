"""Conversation store — abstract + in-memory implementation.

Production implementations live in the backend layer (SQLAlchemy).
The InMemoryConversationStore is for testing and local development.

Ownership contract (IDOR hardening): all history access is scoped to the
conversation's owner. Unknown and foreign conversations are
indistinguishable — both raise ``NotFoundError`` so callers cannot probe
for the existence of other users' conversations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID, uuid4

from narrare_core.chat.contracts import ChatConversation, ChatMessage
from narrare_core.shared.errors import NotFoundError


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
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        """Get the message history for a conversation owned by ``user_id``.

        Raises:
            NotFoundError: The conversation does not exist or is owned by
                another user.
        """
        ...

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
    async def get_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> ChatConversation:
        """Return the metadata of a conversation owned by ``user_id``.

        This is the pre-write ownership gate: callers verify ownership
        BEFORE appending messages, so a foreign or unknown conversation
        fails without any write side effect.

        Raises:
            NotFoundError: The conversation does not exist or is owned by
                another user.
        """
        ...

    @abstractmethod
    async def get_conversation_project_id(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> UUID | None:
        """Return the project_id for an owned conversation, or None.

        ``None`` strictly means the conversation is project-less
        (NOTES-001 §6b).

        Raises:
            NotFoundError: The conversation does not exist or is owned by
                another user.
        """
        ...

    @abstractmethod
    async def clear_history(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> None:
        """Delete all messages in a conversation owned by ``user_id``.

        The conversation itself (metadata row) persists and stays
        readable for its owner.

        Raises:
            NotFoundError: The conversation does not exist or is owned by
                another user.
        """
        ...


class InMemoryConversationStore(ConversationStore):
    """In-memory store — no persistence across restarts.

    Useful for testing and local development without PostgreSQL.
    """

    def __init__(self, *, max_messages: int = 50) -> None:
        self._max_messages = max_messages
        self._messages: dict[UUID, list[ChatMessage]] = {}
        self._conversations: dict[UUID, dict[str, object]] = {}

    def _require_owned_conversation(self, conversation_id: UUID, user_id: UUID) -> None:
        """Ownership gate — foreign and unknown conversations both 404."""
        conv = self._conversations.get(conversation_id)
        if conv is None or conv.get("user_id") != user_id:
            raise NotFoundError("ChatConversation", identifier=str(conversation_id))

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
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        self._require_owned_conversation(conversation_id, user_id)
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

    async def get_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> ChatConversation:
        """Owned conversation metadata — NotFoundError for foreign/unknown."""
        self._require_owned_conversation(conversation_id, user_id)
        conv = self._conversations[conversation_id]
        project_id = conv.get("project_id")
        return ChatConversation(
            id=conversation_id,
            project_id=project_id if isinstance(project_id, UUID) else None,
            user_id=user_id,
        )

    async def get_conversation_project_id(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> UUID | None:
        """Project_id for an owned conversation — None means project-less."""
        self._require_owned_conversation(conversation_id, user_id)
        conv = self._conversations[conversation_id]
        project_id = conv.get("project_id")
        return project_id if isinstance(project_id, UUID) else None

    async def clear_history(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> None:
        """Delete the conversation's messages; keep the conversation itself.

        Mirrors the SQLAlchemy store, where only ``chat_messages`` rows
        are deleted — the ``chat_conversations`` row (and thus ownership)
        persists.
        """
        self._require_owned_conversation(conversation_id, user_id)
        self._messages.pop(conversation_id, None)
