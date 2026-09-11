"""Unit tests for ChatService.get_project_id_for_conversation.

Tests that the service correctly resolves a conversation's project_id,
returning an honest ``None`` for project-less conversations (NOTES-001
§6b). Unknown or foreign conversations raise ``NotFoundError`` (HTTP 404
via the global handler) — ownership scoping (IDOR hardening).

See conftest.py for shared fixtures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from narrare_core.shared.errors import NotFoundError

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

        result = await cast("ChatService", service).get_project_id_for_conversation(
            conv_id, user_id
        )

        assert result == project_id

    async def test_raises_not_found_when_conversation_unknown(
        self,
        service: object,
    ) -> None:
        """Unknown conversations 404 — they must not resolve to project_id None."""
        unknown_conv_id = uuid4()

        with pytest.raises(NotFoundError):
            await cast("ChatService", service).get_project_id_for_conversation(
                unknown_conv_id, uuid4()
            )

    async def test_raises_not_found_when_conversation_foreign(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """Another user's conversation 404s — no existence oracle (IDOR)."""
        owner_id, attacker_id = uuid4(), uuid4()
        conv_id = await cast("InMemoryConversationStore", in_memory_store).create_conversation(
            None, owner_id, "Private"
        )

        with pytest.raises(NotFoundError):
            await cast("ChatService", service).get_project_id_for_conversation(conv_id, attacker_id)


class TestGetHistoryProjectIdPassthrough:
    """The history response pattern: honest None passthrough (no sentinel).

    The router forwards ``get_project_id_for_conversation()`` directly into
    ``ChatHistoryResponse`` — for an owned conversation, ``None`` means
    project-less (NOTES-001 §6b). Unknown/foreign conversations never
    reach this point (they 404 in ``get_history``).
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
        resolved = await cast("ChatService", service).get_project_id_for_conversation(
            conv_id, user_id
        )
        response_project_id = resolved

        assert response_project_id == project_id
        assert response_project_id is not None

    async def test_none_passed_through_for_projectless_conversation(
        self,
        service: object,
        in_memory_store: object,
    ) -> None:
        """Router pattern: ``None`` flows through for project-less conversations."""
        user_id = uuid4()
        conv_id = await cast("InMemoryConversationStore", in_memory_store).create_conversation(
            None, user_id, "Global note chat"
        )

        # Simulate the router: direct passthrough, no sentinel fallback.
        resolved = await cast("ChatService", service).get_project_id_for_conversation(
            conv_id, user_id
        )
        response_project_id = resolved

        assert response_project_id is None
