"""Tests for WritingSessionHandler — WebSocket session message routing.

Covers:
- Mode-aware greeting (interactive_session vs interview_assisted)
- Message routing for all message types
- Direction handling with correct prompt mode and intent per mode
- Interview mode: generate_draft delegates to InterviewDraftGenerator
- Interview mode: generate_draft rejected in interactive_session mode
- Unknown message types return error
- Empty direction returns error
- Timeout and disconnect handling

Shared mocks/helpers (MockWebSocket, ``_make_handler``, stream fakes) live
in ``ws_test_helpers`` so this module stays under the RULE-04 size limit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

from tests.unit.api.writing.ws_test_helpers import (
    MockWebSocket,
    _fake_stream_empty,
    _fake_stream_hello,
    _make_handler,
    stream_kwargs_for_intent,
    wait_for_gateway_calls,
)

if TYPE_CHECKING:
    from fastapi import WebSocket


# ---------------------------------------------------------------------------
# Greeting tests
# ---------------------------------------------------------------------------


class TestGreeting:
    """Mode-aware greeting after WebSocket connection."""

    async def test_interactive_session_greeting_has_message(self) -> None:
        """interactive_session mode sends greeting with message field."""
        handler, *_ = _make_handler(mode="interactive_session")
        ws = MockWebSocket()
        chapter_id = uuid4()
        user_id = uuid4()
        project_id = uuid4()

        await ws.enqueue_end_session()
        await handler.handle(cast("WebSocket", ws), chapter_id, str(user_id), project_id)

        greeting = ws.sent[0]
        assert greeting["type"] == "greeting"
        assert greeting["message"] == "What would you like to write today?"
        assert "session_id" in greeting

    async def test_interview_assisted_greeting_has_mode_interview(self) -> None:
        """interview_assisted mode sends greeting with mode=interview."""
        handler, *_ = _make_handler(mode="interview_assisted")
        ws = MockWebSocket()
        chapter_id = uuid4()
        user_id = uuid4()
        project_id = uuid4()

        await ws.enqueue_end_session()
        await handler.handle(cast("WebSocket", ws), chapter_id, str(user_id), project_id)

        greeting = ws.sent[0]
        assert greeting["type"] == "greeting"
        assert greeting["mode"] == "interview"
        assert "session_id" in greeting
        # Should NOT have the default "message" field
        assert "message" not in greeting


# ---------------------------------------------------------------------------
# Message routing tests
# ---------------------------------------------------------------------------


class TestMessageRouting:
    """Route incoming messages to the correct handler."""

    async def test_unknown_message_type_returns_error(self) -> None:
        """Unknown type sends error response."""
        handler, *_ = _make_handler()
        ws = MockWebSocket()

        await ws.enqueue({"type": "unknown_type"})
        await ws.enqueue_end_session()

        chapter_id = uuid4()
        user_id = uuid4()
        project_id = uuid4()
        await handler.handle(cast("WebSocket", ws), chapter_id, str(user_id), project_id)

        # greeting + error
        assert ws.sent[0]["type"] == "greeting"
        error_msg = ws.sent[1]
        assert error_msg["type"] == "error"
        assert "unknown" in error_msg["message"].lower()

    async def test_empty_direction_returns_error(self) -> None:
        """Empty user_direction content sends error."""
        handler, *_ = _make_handler()
        ws = MockWebSocket()

        await ws.enqueue({"type": "user_direction", "content": "   "})
        await ws.enqueue_end_session()

        await handler.handle(cast("WebSocket", ws), uuid4(), str(uuid4()), uuid4())

        errors = [m for m in ws.sent if m["type"] == "error"]
        assert len(errors) == 1
        assert "empty" in errors[0]["message"].lower()

    async def test_end_session_closes_websocket_and_ends_session(self) -> None:
        """end_session message evicts the session and closes the WebSocket.

        The explicit ``end_session`` message must call
        ``SessionManager.end_session`` with the connection's session id
        (which deletes the cached state) BEFORE closing the transport.
        """
        handler, session_manager, *_ = _make_handler()
        ws = MockWebSocket()

        # Record end_session invocations while preserving the real eviction
        # behaviour (cache.delete on the session store).
        end_session_mock = AsyncMock(wraps=session_manager.end_session)
        session_manager.end_session = end_session_mock  # type: ignore[method-assign]

        await ws.enqueue_end_session()

        await handler.handle(cast("WebSocket", ws), uuid4(), str(uuid4()), uuid4())

        assert ws._closed
        greeting = ws.sent[0]
        assert end_session_mock.await_count == 1
        end_session_mock.assert_awaited_once_with(UUID(greeting["session_id"]))


# ---------------------------------------------------------------------------
# Direction handling — mode-dependent behavior
# ---------------------------------------------------------------------------


class TestDirectionHandling:
    """Direction handling uses correct intent and prompt mode."""

    async def test_interactive_uses_write_intent(self) -> None:
        """interactive_session mode uses LLMIntent.WRITE and mode='interactive'."""
        handler, _, gateway, _ = _make_handler(mode="interactive_session")
        ws = MockWebSocket()

        await ws.enqueue({"type": "user_direction", "content": "Write a scene"})
        await ws.enqueue_end_session()

        await handler.handle(cast("WebSocket", ws), uuid4(), str(uuid4()), uuid4())

        # Verify gateway.stream was called with WRITE intent
        await wait_for_gateway_calls(gateway, 1)
        gateway.stream.assert_called_once()
        call_kwargs = gateway.stream.call_args
        assert call_kwargs.kwargs["intent"].value == "write"

    async def test_interview_uses_chat_intent(self) -> None:
        """interview_assisted mode uses LLMIntent.CHAT and mode='interview'."""
        handler, _, gateway, _ = _make_handler(mode="interview_assisted")
        ws = MockWebSocket()

        await ws.enqueue({"type": "user_direction", "content": "A dog dancing tango"})
        await ws.enqueue_end_session()

        await handler.handle(cast("WebSocket", ws), uuid4(), str(uuid4()), uuid4())

        # Verify gateway.stream was called with CHAT intent
        await wait_for_gateway_calls(gateway, 1)
        gateway.stream.assert_called_once()
        call_kwargs = gateway.stream.call_args
        assert call_kwargs.kwargs["intent"].value == "chat"


# ---------------------------------------------------------------------------
# Generate draft — interview mode only
# ---------------------------------------------------------------------------


class TestGenerateDraft:
    """generate_draft message handling in interview mode."""

    async def test_generate_draft_rejected_in_interactive_mode(self) -> None:
        """generate_draft in interactive_session mode returns unknown type error."""
        handler, *_ = _make_handler(mode="interactive_session")
        ws = MockWebSocket()

        await ws.enqueue({"type": "generate_draft"})
        await ws.enqueue_end_session()

        await handler.handle(cast("WebSocket", ws), uuid4(), str(uuid4()), uuid4())

        errors = [m for m in ws.sent if m["type"] == "error"]
        assert len(errors) == 1
        assert "unknown" in errors[0]["message"].lower()

    async def test_generate_draft_with_no_history_returns_error(self) -> None:
        """generate_draft with empty conversation history returns error."""
        handler, _, gateway, _ = _make_handler(mode="interview_assisted")
        # Override stream to avoid issues
        gateway.stream = Mock(side_effect=_fake_stream_empty)
        ws = MockWebSocket()

        # Send generate_draft without any prior direction
        await ws.enqueue({"type": "generate_draft"})
        await ws.enqueue_end_session()

        await handler.handle(cast("WebSocket", ws), uuid4(), str(uuid4()), uuid4())

        errors = [m for m in ws.sent if m["type"] == "error"]
        assert any("no interview answers" in e["message"].lower() for e in errors)

    async def test_generate_draft_with_history_streams_draft(self) -> None:
        """generate_draft with prior Q&A streams a complete draft."""
        handler, _, gateway, _ = _make_handler(mode="interview_assisted")
        # First call: interview question (from user_direction)
        # Second call: draft generation (from generate_draft)
        gateway.stream = Mock(side_effect=_fake_stream_hello)
        ws = MockWebSocket()

        # Simulate an interview exchange
        await ws.enqueue({"type": "user_direction", "content": "I want a chapter about a dog"})
        await ws.enqueue({"type": "generate_draft"})
        await ws.enqueue_end_session()

        await handler.handle(cast("WebSocket", ws), uuid4(), str(uuid4()), uuid4())

        # Should have greeting, text_chunk(s), text_done from direction,
        # then text_chunk(s), draft_done from generate_draft
        draft_done = [m for m in ws.sent if m["type"] == "draft_done"]
        assert len(draft_done) == 1
        assert draft_done[0]["word_count"] > 0

    async def test_generate_draft_uses_write_intent(self) -> None:
        """generate_draft calls LLM with WRITE intent and enforced limits."""
        handler, _, gateway, _ = _make_handler(mode="interview_assisted")
        gateway.stream = Mock(side_effect=_fake_stream_hello)
        ws = MockWebSocket()

        # First: one interview exchange
        await ws.enqueue({"type": "user_direction", "content": "A mystery novel"})
        # Then: generate draft
        await ws.enqueue({"type": "generate_draft"})
        await ws.enqueue_end_session()

        await handler.handle(cast("WebSocket", ws), uuid4(), str(uuid4()), uuid4())

        # gateway.stream called twice:
        # 1st: CHAT for interview question
        # 2nd: WRITE for draft generation
        await wait_for_gateway_calls(gateway, 2)
        assert gateway.stream.call_count == 2
        draft_kwargs = stream_kwargs_for_intent(gateway, "write")
        assert draft_kwargs["intent"].value == "write"
