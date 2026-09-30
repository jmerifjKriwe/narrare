"""Conversation history read/maintenance mixin for ``ChatService`` (RULE-04).

Extracted from ``chat_service.py`` to respect the file-size hard limit
(the file had no headroom for the ADR-089 escalation seam). Holds the
owner-scoped history operations: reading history, resolving a
conversation's project id, and clearing history. The chat-flow
responsibility (``ask`` / ``ensure_resolved``) stays on the host class.

The mixin relies on the host-provided collaborator:

* ``self._store`` — the ``SQLAlchemyConversationStore`` (persistence).

Mirrors the ``prompts/_history_compare_mixin.py`` extraction pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.chat.contracts import ChatMessage


class ChatHistoryMixin:
    """Owner-scoped history operations (mixed into ``ChatService``).

    Relies on the host-provided collaborator (declared for type checkers):
    ``_store`` — assigned by :class:`~narrare.chat.chat_service.ChatService`.
    """

    if TYPE_CHECKING:
        _store: SQLAlchemyConversationStore

    async def get_history(
        self,
        conversation_id: UUID,
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        """Get conversation history for its owner.

        Args:
            conversation_id: The conversation UUID.
            user_id: The authenticated user — must own the conversation.
            limit: Maximum number of messages (newest first). Defaults to 50.

        Returns:
            List of ChatMessage dataclasses ordered by creation time.

        Raises:
            NotFoundError: The conversation does not exist or is owned by
                another user (mapped to HTTP 404).
        """
        return await self._store.get_history(conversation_id, user_id, limit=limit)

    async def get_project_id_for_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> UUID | None:
        """Get the project_id associated with a conversation.

        Args:
            conversation_id: The conversation UUID.
            user_id: The authenticated user — must own the conversation.

        Returns:
            The project UUID, or ``None`` for a project-less conversation
            (NOTES-001 §6b).

        Raises:
            NotFoundError: The conversation does not exist or is owned by
                another user (mapped to HTTP 404).
        """
        return await self._store.get_conversation_project_id(conversation_id, user_id)

    async def clear_history(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> None:
        """Clear conversation history (deletes all messages).

        Args:
            conversation_id: The conversation UUID.
            user_id: The authenticated user — must own the conversation.

        Raises:
            NotFoundError: The conversation does not exist or is owned by
                another user (mapped to HTTP 404).
        """
        await self._store.clear_history(conversation_id, user_id)
