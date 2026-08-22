"""Unit tests for narrare.chat.router — SSE streaming and history CRUD.

Tests the thin delegation layer (RULE-06) using a ``FakeChatService``
that implements ``ChatServiceProtocol`` (ADR-030 Fake pattern).

Each router endpoint is called directly — no FastAPI app or HTTP layer.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare.chat.router import chat, clear_history, get_history
from narrare.chat.schemas import ChatRequest as APIChatRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.chat.contracts import ChatMessage, ChatRequest


# ---------------------------------------------------------------------------
# FakeChatService — implements ChatServiceProtocol (ADR-030)
# ---------------------------------------------------------------------------


class FakeChatService:
    """In-memory Fake for ChatServiceProtocol.

    Allows configuring stream events, history, and project_id per test.
    Records clear_history calls for verification.
    """

    def __init__(self) -> None:
        self._events: list[dict[str, object]] = []
        self._history: list[ChatMessage] = []
        self._project_id: UUID | None = None
        self.cleared_ids: list[UUID] = []

    def set_stream_events(self, *events: dict[str, object]) -> None:
        """Pre-configure the events that ``ask()`` will stream."""
        self._events = list(events)

    def set_history(self, *messages: ChatMessage) -> None:
        """Pre-configure messages returned by ``get_history()``."""
        self._history = list(messages)

    def set_project_id(self, project_id: UUID | None) -> None:
        """Set the project_id returned by ``get_project_id_for_conversation()``."""
        self._project_id = project_id

    async def ask(
        self,
        request: ChatRequest,
        user_id: UUID,
    ) -> AsyncIterator[dict[str, object]]:
        """Return a pre-configured async stream of events."""

        async def _stream() -> AsyncIterator[dict[str, object]]:
            for event in self._events:
                yield event

        return _stream()

    async def get_history(
        self,
        conversation_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        return list(self._history)

    async def get_project_id_for_conversation(
        self,
        conversation_id: UUID,
    ) -> UUID | None:
        return self._project_id

    async def clear_history(
        self,
        conversation_id: UUID,
    ) -> None:
        self.cleared_ids.append(conversation_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_api_request(message: str = "Hello!") -> APIChatRequest:
    """Create an API ChatRequest with sensible defaults."""
    return APIChatRequest(project_id=uuid4(), message=message)


async def _collect_sse_chunks(response: object) -> list[str]:
    """Consume a StreamingResponse body iterator and return chunks."""
    chunks: list[str] = []
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        chunks.append(chunk if isinstance(chunk, str) else chunk.decode())
    return chunks


# ---------------------------------------------------------------------------
# POST /chat — SSE streaming
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    """Tests for the chat SSE streaming endpoint."""

    async def test_streams_meta_token_done_as_sse(self) -> None:
        """Happy path: meta, token, and done events produce SSE-formatted chunks."""
        from narrare.chat.chat_service import ChatService

        fake = FakeChatService()
        fake.set_stream_events(
            {"type": "meta", "conversation_id": "conv-1", "request_id": "req-1"},
            {"type": "token", "text": "Hello "},
            {"type": "token", "text": "world!"},
            {"type": "done", "usage": {"total_tokens": 10}},
        )

        response = await chat(
            request=_make_api_request(),
            user_id=str(uuid4()),
            service=cast("ChatService", fake),
        )

        chunks = await _collect_sse_chunks(response)

        assert len(chunks) == 4
        assert chunks[0].startswith("event: meta\n")
        assert chunks[1].startswith("event: token\n")
        assert chunks[2].startswith("event: token\n")
        assert chunks[3].startswith("event: done\n")

        # Verify token data is valid JSON
        token_data = json.loads(chunks[1].split("data: ", 1)[1].strip())
        assert token_data["text"] == "Hello "

        done_data = json.loads(chunks[3].split("data: ", 1)[1].strip())
        assert done_data["usage"] == {"total_tokens": 10}

    async def test_serializes_non_string_values_in_meta(self) -> None:
        """_serialize_for_json converts non-string values to strings."""
        from narrare.chat.chat_service import ChatService

        fake = FakeChatService()
        fake.set_stream_events(
            {"type": "meta", "conversation_id": 12345, "request_id": "req-1"},
        )

        response = await chat(
            request=_make_api_request(),
            user_id=str(uuid4()),
            service=cast("ChatService", fake),
        )

        chunks = await _collect_sse_chunks(response)

        meta_data = json.loads(chunks[0].split("data: ", 1)[1].strip())
        # Non-string 12345 should have been converted to "12345"
        assert meta_data["conversation_id"] == "12345"

    async def test_unknown_event_type_produces_no_chunk(self) -> None:
        """Events with unknown types are silently skipped."""
        from narrare.chat.chat_service import ChatService

        fake = FakeChatService()
        fake.set_stream_events(
            {"type": "meta", "conversation_id": "c1", "request_id": "r1"},
            {"type": "unknown", "text": "mystery"},
            {"type": "done", "usage": {}},
        )

        response = await chat(
            request=_make_api_request(),
            user_id=str(uuid4()),
            service=cast("ChatService", fake),
        )

        chunks = await _collect_sse_chunks(response)

        # Only meta and done produce chunks — unknown is skipped
        assert len(chunks) == 2


# ---------------------------------------------------------------------------
# GET /chat/history/{conversation_id}
# ---------------------------------------------------------------------------


class TestGetHistoryEndpoint:
    """Tests for the get_history endpoint."""

    async def test_returns_messages_with_real_project_id(self) -> None:
        """History endpoint returns messages and resolves project_id."""
        from narrare.chat.chat_service import ChatService
        from narrare_core.chat.contracts import ChatMessage

        conv_id = uuid4()
        project_id = uuid4()

        fake = FakeChatService()
        fake.set_history(
            ChatMessage(
                conversation_id=conv_id,
                role="user",
                content="Question?",
                created_at="2026-01-01T00:00:00Z",
            ),
            ChatMessage(
                conversation_id=conv_id,
                role="assistant",
                content="Answer!",
                created_at="2026-01-02T00:00:00Z",
            ),
        )
        fake.set_project_id(project_id)

        result = await get_history(
            conversation_id=conv_id,
            user_id=str(uuid4()),
            service=cast("ChatService", fake),
        )

        assert result.conversation_id == conv_id
        assert result.project_id == project_id
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        assert result.messages[1].role == "assistant"

    async def test_project_id_is_none_when_project_not_found(self) -> None:
        """When project_id resolves to None, the response exposes None honestly (NOTES-001 §8)."""
        from narrare.chat.chat_service import ChatService

        conv_id = uuid4()

        fake = FakeChatService()
        fake.set_project_id(None)

        result = await get_history(
            conversation_id=conv_id,
            user_id=str(uuid4()),
            service=cast("ChatService", fake),
        )

        assert result.project_id is None


# ---------------------------------------------------------------------------
# DELETE /chat/history/{conversation_id}
# ---------------------------------------------------------------------------


class TestClearHistoryEndpoint:
    """Tests for the clear_history endpoint."""

    async def test_clears_and_returns_delete_response(self) -> None:
        """clear_history delegates to service and returns confirmation."""
        from narrare.chat.chat_service import ChatService

        conv_id = uuid4()

        fake = FakeChatService()

        result = await clear_history(
            conversation_id=conv_id,
            user_id=str(uuid4()),
            service=cast("ChatService", fake),
        )

        assert result.conversation_id == conv_id
        assert result.deleted is True
        assert conv_id in fake.cleared_ids
