"""Unit tests for ChatService.get_project_id_for_conversation.

Tests that the service correctly resolves a conversation's project_id,
with an explicit fallback to zero UUID when the conversation is not found.

See conftest.py for shared fixtures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

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


class TestGetHistoryEndpointProjectId:
    """Integration-style tests verifying the router fallback behavior.

    These tests verify the logic pattern used in the router:
    - real project_id when available
    - UUID(int=0) fallback when conversation not found
    """

    async def test_router_pattern_real_project_id(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """Router pattern: uses real project_id when conversation exists."""
        project_id = uuid4()
        user_id = uuid4()
        conv_id = await cast("InMemoryConversationStore", in_memory_store).create_conversation(
            project_id, user_id, "Hello"
        )

        # Simulate the router logic
        resolved = await cast("ChatService", service).get_project_id_for_conversation(conv_id)
        response_project_id = resolved if resolved is not None else UUID(int=0)

        assert response_project_id == project_id
        assert response_project_id != UUID(int=0)

    async def test_router_pattern_fallback_zero_uuid(
        self,
        service: object,
    ) -> None:
        """Router pattern: falls back to UUID(int=0) when not found."""
        unknown_conv_id = uuid4()

        # Simulate the router logic
        resolved = await cast("ChatService", service).get_project_id_for_conversation(
            unknown_conv_id
        )
        response_project_id = resolved if resolved is not None else UUID(int=0)

        assert response_project_id == UUID(int=0)
