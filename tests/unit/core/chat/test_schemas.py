"""Unit tests for narrare_core.chat.schemas — pure Pydantic models.

Tests instantiation, defaults, and validation for all shared chat schemas.
No I/O, no DB, no LLM — pure data-model tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.chat.schemas import (
    ChatHistoryResponseSchema,
    ChatMessageSchema,
    ChatRequestSchema,
    ChatResponseSchema,
)

# ---------------------------------------------------------------------------
# ChatMessageSchema
# ---------------------------------------------------------------------------


class TestChatMessageSchema:
    """Tests for ChatMessageSchema — single message data model."""

    def test_valid_user_message(self) -> None:
        """A user message with all required fields instantiates correctly."""
        conv_id = uuid4()

        msg = ChatMessageSchema(
            conversation_id=conv_id,
            role="user",
            content="Hello world",
        )

        assert msg.conversation_id == conv_id
        assert msg.role == "user"
        assert msg.content == "Hello world"
        assert msg.created_at == ""

    def test_valid_assistant_message(self) -> None:
        """An assistant message with created_at instantiates correctly."""
        msg = ChatMessageSchema(
            conversation_id=uuid4(),
            role="assistant",
            content="Hi there!",
            created_at="2026-01-01T00:00:00Z",
        )

        assert msg.role == "assistant"
        assert msg.created_at == "2026-01-01T00:00:00Z"

    def test_invalid_role_rejected(self) -> None:
        """Role must match ^(user|assistant)$ pattern."""
        with pytest.raises(ValueError, match="String should match pattern"):
            ChatMessageSchema(
                conversation_id=uuid4(),
                role="system",
                content="invalid role",
            )


# ---------------------------------------------------------------------------
# ChatRequestSchema
# ---------------------------------------------------------------------------


class TestChatRequestSchema:
    """Tests for ChatRequestSchema — chat request data model."""

    def test_valid_request_new_conversation(self) -> None:
        """A request without conversation_id starts a new conversation."""
        req = ChatRequestSchema(
            project_id=uuid4(),
            message="Tell me about my novel.",
        )

        assert req.conversation_id is None

    def test_valid_request_existing_conversation(self) -> None:
        """A request with conversation_id continues an existing conversation."""
        conv_id = uuid4()

        req = ChatRequestSchema(
            project_id=uuid4(),
            message="Follow up question",
            conversation_id=conv_id,
        )

        assert req.conversation_id == conv_id

    def test_empty_message_rejected(self) -> None:
        """Message must have at least 1 character (min_length=1)."""
        with pytest.raises(ValueError, match="at least 1 character"):
            ChatRequestSchema(
                project_id=uuid4(),
                message="",
            )

    def test_message_exceeding_max_length_rejected(self) -> None:
        """Message must not exceed 4000 characters (max_length=4000)."""
        with pytest.raises(ValueError, match="at most 4000 character"):
            ChatRequestSchema(
                project_id=uuid4(),
                message="x" * 4001,
            )

    def test_message_at_max_length_accepted(self) -> None:
        """A message of exactly 4000 characters is accepted."""
        req = ChatRequestSchema(
            project_id=uuid4(),
            message="x" * 4000,
        )

        assert len(req.message) == 4000


# ---------------------------------------------------------------------------
# ChatResponseSchema
# ---------------------------------------------------------------------------


class TestChatResponseSchema:
    """Tests for ChatResponseSchema — response metadata."""

    def test_valid_response(self) -> None:
        """A response with conversation_id and message_id instantiates correctly."""
        conv_id = uuid4()
        msg_id = uuid4()

        resp = ChatResponseSchema(
            conversation_id=conv_id,
            message_id=msg_id,
        )

        assert resp.conversation_id == conv_id
        assert resp.message_id == msg_id


# ---------------------------------------------------------------------------
# ChatHistoryResponseSchema
# ---------------------------------------------------------------------------


class TestChatHistoryResponseSchema:
    """Tests for ChatHistoryResponseSchema — full history response."""

    def test_empty_history(self) -> None:
        """A history response with no messages defaults timestamps to empty."""
        conv_id = uuid4()

        resp = ChatHistoryResponseSchema(
            conversation_id=conv_id,
            messages=[],
        )

        assert resp.conversation_id == conv_id
        assert resp.messages == []
        assert resp.created_at == ""
        assert resp.updated_at == ""

    def test_history_with_messages(self) -> None:
        """A history response with messages preserves order."""
        conv_id = uuid4()

        msgs = [
            ChatMessageSchema(conversation_id=conv_id, role="user", content="Q"),
            ChatMessageSchema(conversation_id=conv_id, role="assistant", content="A"),
        ]

        resp = ChatHistoryResponseSchema(
            conversation_id=conv_id,
            messages=msgs,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
        )

        assert len(resp.messages) == 2
        assert resp.messages[0].role == "user"
        assert resp.messages[1].role == "assistant"
        assert resp.created_at == "2026-01-01T00:00:00Z"
