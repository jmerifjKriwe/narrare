"""Unit tests for narrare.chat.schemas — FastAPI Pydantic schemas.

Tests instantiation, defaults, and validation for all API-level chat schemas.
No I/O, no DB — pure data-model tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.chat.schemas import (
    ChatDeleteResponse,
    ChatDoneEvent,
    ChatHistoryResponse,
    ChatMessageSchema,
    ChatMetaEvent,
    ChatRequest,
    ChatTokenEvent,
)

# ---------------------------------------------------------------------------
# ChatRequest
# ---------------------------------------------------------------------------


class TestChatRequest:
    """Tests for the API ChatRequest schema."""

    def test_valid_request_new_conversation(self) -> None:
        """A request without conversation_id starts a new conversation."""
        req = ChatRequest(
            project_id=uuid4(),
            message="How do I write dialogue?",
        )

        assert req.conversation_id is None

    def test_valid_request_existing_conversation(self) -> None:
        """A request with conversation_id continues an existing conversation."""
        conv_id = uuid4()

        req = ChatRequest(
            project_id=uuid4(),
            message="More questions",
            conversation_id=conv_id,
        )

        assert req.conversation_id == conv_id

    def test_empty_message_rejected(self) -> None:
        """Message must have at least 1 character."""
        with pytest.raises(ValueError, match="at least 1 character"):
            ChatRequest(project_id=uuid4(), message="")

    def test_message_exceeding_max_length_rejected(self) -> None:
        """Message must not exceed 4000 characters."""
        with pytest.raises(ValueError, match="at most 4000 character"):
            ChatRequest(project_id=uuid4(), message="x" * 4001)


class TestChatRequestNotesExtension:
    """NOTES-001 §6b: project_id optional + note_id context attachment."""

    def test_legacy_request_with_project_unchanged(self) -> None:
        """Regression: the pre-NOTES-001 shape validates identically."""
        project_id = uuid4()
        req = ChatRequest(project_id=project_id, message="How do I write dialogue?")
        assert req.project_id == project_id
        assert req.note_id is None

    def test_projectless_request_valid(self) -> None:
        req = ChatRequest(message="Discuss this global note")
        assert req.project_id is None

    def test_note_id_optional(self) -> None:
        note_id = uuid4()
        req = ChatRequest(message="Discuss", note_id=note_id)
        assert req.note_id == note_id


# ---------------------------------------------------------------------------
# ChatMessageSchema
# ---------------------------------------------------------------------------


class TestChatMessageSchema:
    """Tests for the API ChatMessageSchema."""

    def test_valid_user_message(self) -> None:
        """A user message with defaults instantiates correctly."""
        msg = ChatMessageSchema(
            message_id=uuid4(),
            role="user",
            content="Hello",
        )

        assert msg.created_at == ""

    def test_valid_assistant_message_with_timestamp(self) -> None:
        """An assistant message with timestamp instantiates correctly."""
        msg = ChatMessageSchema(
            message_id=uuid4(),
            role="assistant",
            content="World",
            created_at="2026-01-01T00:00:00Z",
        )

        assert msg.created_at == "2026-01-01T00:00:00Z"

    def test_invalid_role_rejected(self) -> None:
        """Role must match ^(user|assistant)$ pattern."""
        with pytest.raises(ValueError, match="String should match pattern"):
            ChatMessageSchema(
                message_id=uuid4(),
                role="admin",
                content="invalid",
            )


# ---------------------------------------------------------------------------
# ChatHistoryResponse
# ---------------------------------------------------------------------------


class TestChatHistoryResponse:
    """Tests for the API ChatHistoryResponse."""

    def test_empty_history_with_defaults(self) -> None:
        """An empty history response has default timestamps."""
        conv_id = uuid4()
        project_id = uuid4()

        resp = ChatHistoryResponse(
            conversation_id=conv_id,
            project_id=project_id,
            messages=[],
        )

        assert resp.created_at == ""
        assert resp.updated_at == ""

    def test_history_with_messages(self) -> None:
        """A history response preserves message list."""
        msgs = [
            ChatMessageSchema(message_id=uuid4(), role="user", content="Q"),
            ChatMessageSchema(message_id=uuid4(), role="assistant", content="A"),
        ]

        resp = ChatHistoryResponse(
            conversation_id=uuid4(),
            project_id=uuid4(),
            messages=msgs,
        )

        assert len(resp.messages) == 2


class TestChatHistoryResponseOptionalProject:
    """NOTES-001 §6b: history exposes an honest nullable project_id."""

    def test_project_id_may_be_none(self) -> None:
        resp = ChatHistoryResponse(
            conversation_id=uuid4(),
            project_id=None,
            messages=[],
        )
        assert resp.project_id is None


# ---------------------------------------------------------------------------
# ChatDeleteResponse
# ---------------------------------------------------------------------------


class TestChatDeleteResponse:
    """Tests for ChatDeleteResponse."""

    def test_default_deleted_is_true(self) -> None:
        """The deleted flag defaults to True."""
        conv_id = uuid4()

        resp = ChatDeleteResponse(conversation_id=conv_id)

        assert resp.deleted is True
        assert resp.conversation_id == conv_id


# ---------------------------------------------------------------------------
# SSE Event Schemas
# ---------------------------------------------------------------------------


class TestSSEEventSchemas:
    """Tests for SSE event Pydantic models."""

    def test_meta_event_defaults(self) -> None:
        """ChatMetaEvent has type='meta' by default."""
        event = ChatMetaEvent(
            conversation_id=uuid4(),
            request_id=uuid4(),
        )

        assert event.type == "meta"

    def test_token_event_defaults(self) -> None:
        """ChatTokenEvent has type='token' by default."""
        event = ChatTokenEvent(text="partial")

        assert event.type == "token"
        assert event.text == "partial"

    def test_done_event_defaults(self) -> None:
        """ChatDoneEvent has type='done' and empty usage by default."""
        event = ChatDoneEvent()

        assert event.type == "done"
        assert event.usage == {}

    def test_done_event_with_usage(self) -> None:
        """ChatDoneEvent accepts usage stats."""
        event = ChatDoneEvent(usage={"total_tokens": 42})

        assert event.usage == {"total_tokens": 42}
