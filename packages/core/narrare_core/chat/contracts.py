"""Chat service contracts — Free-Form Chat for Writing Craft.

ADR-024: Free-Form Chat for Writing Craft
CR-AUFG-02-03: Free-Form-Chat Feature
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID


@dataclass
class ChatMessage:
    """A single chat message in a conversation."""

    conversation_id: UUID
    role: str  # "user" or "assistant"
    content: str
    created_at: str = field(default="")


@dataclass
class ChatRequest:
    """Request to send a chat message.

    ``project_id`` is optional since NOTES-001: chatting about a global note
    has no project (KB/project context tiers are skipped then). ``note_id``
    attaches a scratchpad note as runtime context (spec §6b).
    """

    project_id: UUID | None = None
    message: str = ""
    conversation_id: UUID | None = None
    note_id: UUID | None = None


@dataclass
class ChatResponse:
    """Response metadata for a chat request."""

    conversation_id: UUID
    message_id: UUID


@dataclass
class ChatConversation:
    """A chat conversation scoped to a project."""

    id: UUID
    project_id: UUID
    user_id: UUID
    title: str = field(default="")
    created_at: str = field(default="")
    updated_at: str = field(default="")


class ChatServiceProtocol(Protocol):
    """Service protocol for free-form chat.

    Follows RULE-03 (Contract first) and RULE-13 (streaming interface).
    """

    async def ask(
        self,
        request: ChatRequest,
        user_id: UUID,
    ) -> AsyncIterator[dict[str, object]]:
        """Process a chat message and stream the response.

        Yields SSE events: meta, token..., done
        """
        ...

    async def get_history(
        self,
        conversation_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        """Get conversation history."""
        ...

    async def get_project_id_for_conversation(
        self,
        conversation_id: UUID,
    ) -> UUID | None:
        """Get the project_id associated with a conversation.

        Returns the project UUID, or None if the conversation does not exist.
        """
        ...

    async def clear_history(
        self,
        conversation_id: UUID,
    ) -> None:
        """Clear conversation history."""
        ...
