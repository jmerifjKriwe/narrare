"""Unit tests for narrare.chat.router — SSE streaming and history CRUD.

Tests the thin delegation layer (RULE-06) using a ``FakeChatService``
that implements ``ChatServiceProtocol`` (ADR-030 Fake pattern).

Each router endpoint is called directly — no FastAPI app or HTTP layer.
The NotFoundError raised for foreign/unknown conversations is mapped to
HTTP 404 by the global NarrareError handler (covered at app level).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest
from tests.unit.api.chat.conftest import FakeChatService

from narrare.chat.router import chat, clear_history, get_history
from narrare.chat.schemas import ChatRequest as APIChatRequest
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from narrare.chat.chat_service import ChatService


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

    async def test_chat_raises_not_found_before_stream_starts(self) -> None:
        """IDOR write regression: a foreign/unknown conversation 404s.

        ``ask()`` must run BEFORE the StreamingResponse is created — a
        NotFoundError surfacing inside the body iterator would fire after
        the 200 headers (broken stream), not as HTTP 404 via the global
        NarrareError handler.
        """
        fake = FakeChatService()
        fake.set_ask_error(NotFoundError("ChatConversation", identifier=str(uuid4())))

        with pytest.raises(NotFoundError):
            await chat(
                request=_make_api_request(),
                user_id=str(uuid4()),
                service=cast("ChatService", fake),
            )


# ---------------------------------------------------------------------------
# GET /chat/history/{conversation_id}
# ---------------------------------------------------------------------------


class TestGetHistoryEndpoint:
    """Tests for the get_history endpoint."""

    async def test_returns_messages_with_real_project_id(self) -> None:
        """History endpoint returns messages and resolves project_id."""
        from narrare_core.chat.contracts import ChatMessage

        conv_id = uuid4()
        project_id = uuid4()
        msg_ids = (uuid4(), uuid4())

        fake = FakeChatService()
        fake.set_history(
            ChatMessage(
                conversation_id=conv_id,
                role="user",
                content="Question?",
                created_at="2026-01-01T00:00:00Z",
                message_id=msg_ids[0],
            ),
            ChatMessage(
                conversation_id=conv_id,
                role="assistant",
                content="Answer!",
                created_at="2026-01-02T00:00:00Z",
                message_id=msg_ids[1],
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
        # Regression (W4): each message must report its OWN id — previously
        # every row reported the conversation id as message_id.
        assert [m.message_id for m in result.messages] == list(msg_ids)

    async def test_project_id_is_none_when_project_not_found(self) -> None:
        """When project_id resolves to None, the response exposes None honestly (NOTES-001 §8)."""

        conv_id = uuid4()

        fake = FakeChatService()
        fake.set_project_id(None)

        result = await get_history(
            conversation_id=conv_id,
            user_id=str(uuid4()),
            service=cast("ChatService", fake),
        )

        assert result.project_id is None

    async def test_get_history_with_owner_user_returns_history(self) -> None:
        """Owner access: the authenticated owner still receives the history (HTTP 200)."""
        from narrare_core.chat.contracts import ChatMessage

        owner_id = uuid4()
        conv_id = uuid4()

        fake = FakeChatService()
        fake.set_owner(owner_id)
        fake.set_history(
            ChatMessage(
                conversation_id=conv_id,
                role="user",
                content="Owner question",
                created_at="2026-01-01T00:00:00Z",
                message_id=uuid4(),
            )
        )
        fake.set_project_id(uuid4())

        result = await get_history(
            conversation_id=conv_id,
            user_id=str(owner_id),
            service=cast("ChatService", fake),
        )

        assert result.conversation_id == conv_id
        assert len(result.messages) == 1
        assert result.messages[0].content == "Owner question"

    async def test_get_history_with_foreign_user_raises_not_found(self) -> None:
        """IDOR regression: user B reading user A's conversation gets 404.

        The endpoint must forward the authenticated user_id so the service
        can scope the lookup; NotFoundError is mapped to HTTP 404 by the
        global NarrareError handler.
        """

        owner_id = uuid4()
        attacker_id = uuid4()
        conv_id = uuid4()

        fake = FakeChatService()
        fake.set_owner(owner_id)
        fake.set_history()  # would leak if returned

        with pytest.raises(NotFoundError):
            await get_history(
                conversation_id=conv_id,
                user_id=str(attacker_id),
                service=cast("ChatService", fake),
            )


# ---------------------------------------------------------------------------
# DELETE /chat/history/{conversation_id}
# ---------------------------------------------------------------------------


class TestClearHistoryEndpoint:
    """Tests for the clear_history endpoint."""

    async def test_clears_and_returns_delete_response(self) -> None:
        """clear_history delegates to service and returns confirmation."""

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

    async def test_clear_history_with_owner_user_clears(self) -> None:
        """Owner access: the authenticated owner can delete (HTTP 200/204)."""

        owner_id = uuid4()
        conv_id = uuid4()

        fake = FakeChatService()
        fake.set_owner(owner_id)

        result = await clear_history(
            conversation_id=conv_id,
            user_id=str(owner_id),
            service=cast("ChatService", fake),
        )

        assert result.conversation_id == conv_id
        assert result.deleted is True
        assert conv_id in fake.cleared_ids

    async def test_clear_history_with_foreign_user_raises_not_found(self) -> None:
        """IDOR regression: user B deleting user A's conversation gets 404.

        NotFoundError propagates to the global NarrareError handler (404);
        the conversation must not be cleared for a non-owner.
        """

        owner_id = uuid4()
        attacker_id = uuid4()
        conv_id = uuid4()

        fake = FakeChatService()
        fake.set_owner(owner_id)

        with pytest.raises(NotFoundError):
            await clear_history(
                conversation_id=conv_id,
                user_id=str(attacker_id),
                service=cast("ChatService", fake),
            )

        assert conv_id not in fake.cleared_ids
