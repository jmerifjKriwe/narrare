"""Unit tests for ChatService.get_project_id_for_conversation.

Tests that the service correctly resolves a conversation's project_id,
returning an honest ``None`` for project-less conversations (NOTES-001
§6b) and for unknown conversations — the router passes the value through
unchanged, no sentinel.

See conftest.py for shared fixtures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

if TYPE_CHECKING:
    from narrare.chat.chat_service import ChatService
    from narrare_core.chat.conversation_store import InMemoryConversationStore


class TestGetProjectIdForConversation:
    """Tests for get_project_id_for_conversation — project resolution."""

    async def test_returns_project_id_when_conversation_exists(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """Response contains correct project_id when conversation has a project."""
        project_id = uuid4()
        user_id = uuid4()
        conv_id = await cast("InMemoryConversationStore", in_memory_store).create_conversation(
            project_id, user_id, "Hello"
        )

        result = await cast("ChatService", service).get_project_id_for_conversation(conv_id)

        assert result == project_id

    async def test_returns_none_when_conversation_not_found(
        self,
        service: object,
    ) -> None:
        """Response falls back to None when conversation does not exist."""
        unknown_conv_id = uuid4()

        result = await cast("ChatService", service).get_project_id_for_conversation(unknown_conv_id)

        assert result is None


class TestGetHistoryProjectIdPassthrough:
    """The history response pattern: honest None passthrough (no sentinel).

    The router forwards ``get_project_id_for_conversation()`` directly into
    ``ChatHistoryResponse`` — ``None`` means project-less (NOTES-001 §6b)
    or unknown conversation.
    """

    async def test_project_id_passed_through_when_conversation_exists(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """Router pattern: the real project_id flows through unchanged."""
        project_id = uuid4()
        user_id = uuid4()
        conv_id = await cast("InMemoryConversationStore", in_memory_store).create_conversation(
            project_id, user_id, "Hello"
        )

        # Simulate the router: direct passthrough, no sentinel fallback.
        resolved = await cast("ChatService", service).get_project_id_for_conversation(conv_id)
        response_project_id = resolved

        assert response_project_id == project_id
        assert response_project_id is not None

    async def test_none_passed_through_when_conversation_not_found(
        self,
        service: object,
    ) -> None:
        """Router pattern: ``None`` flows through for unknown conversations."""
        unknown_conv_id = uuid4()

        # Simulate the router: direct passthrough, no sentinel fallback.
        resolved = await cast("ChatService", service).get_project_id_for_conversation(
            unknown_conv_id
        )
        response_project_id = resolved

        assert response_project_id is None
