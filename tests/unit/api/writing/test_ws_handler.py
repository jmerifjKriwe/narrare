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
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.prompts.context import PromptContext

from typing import Any
from unittest.mock import Mock
from uuid import uuid4

from fastapi import WebSocketDisconnect

from narrare.writing._ws_cache import InMemorySessionCache
from narrare.writing.ws_handler import WritingSessionHandler
from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.writing.session_manager import SessionManager

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockWebSocket:
    """Simplified async WebSocket mock for unit tests.

    After ``close()`` is called, ``receive_json()`` raises
    ``WebSocketDisconnect`` to simulate real WebSocket behaviour.
    """

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self._incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._closed = False

    async def accept(self) -> None:
        """Accept the WebSocket connection."""

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)

    async def receive_json(self) -> dict[str, Any]:
        if self._closed:
            raise WebSocketDisconnect()
        return await self._incoming.get()

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self._closed = True

    async def receive_text(self) -> str:
        return "{}"

    async def send_text(self, message: str) -> None:
        pass

    async def enqueue(self, message: dict[str, Any]) -> None:
        await self._incoming.put(message)

    async def enqueue_end_session(self) -> None:
        """Enqueue an end_session message to break the message loop."""
        await self._incoming.put({"type": "end_session"})

    async def enqueue_disconnect(self) -> None:
        """Enqueue a sentinel that raises WebSocketDisconnect."""
        await self._incoming.put({"__disconnect__": True})


class _FakeComposer:
    """Stub PromptComposer that returns a fixed prompt."""

    async def build(
        self,
        intent: LLMIntent,
        context: PromptContext,
        *,
        db_content: str | None = None,
        user_prompt: str = "",
    ) -> ComposedPrompt:
        return ComposedPrompt(system="system-prompt", user="user-prompt")


async def _fake_stream_empty(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
    """Yield a single final chunk with empty text."""
    yield StreamChunk(text="", is_final=True, usage=TokenUsage(0, 0, 0))


async def _fake_stream_hello(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
    """Yield text chunks then a final chunk."""
    yield StreamChunk(text="Hello ")
    yield StreamChunk(text="world!", is_final=True, usage=TokenUsage(10, 20, 30))


def _make_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=100,
    )


def _make_handler(
    mode: str = "interactive_session",
) -> tuple[WritingSessionHandler, SessionManager, Mock, _FakeComposer]:
    """Create a WritingSessionHandler with mock dependencies."""
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    gateway = Mock()
    # Use Mock (not AsyncMock) for stream — code does `async for` directly
    gateway.stream = Mock(side_effect=_fake_stream_hello)
    composer = _FakeComposer()
    config = _make_config()
    pipeline = Mock()

    handler = WritingSessionHandler(
        session_manager=session_manager,
        pipeline=pipeline,
        gateway=gateway,
        composer=composer,  # type: ignore[assignment]
        config=config,
        mode=mode,
    )
    return handler, session_manager, gateway, composer


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
        await handler.handle(ws, chapter_id, str(user_id), project_id)  # type: ignore[arg-type]

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
        await handler.handle(ws, chapter_id, str(user_id), project_id)  # type: ignore[arg-type]

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
        await handler.handle(ws, chapter_id, str(user_id), project_id)  # type: ignore[arg-type]

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

        await handler.handle(ws, uuid4(), str(uuid4()), uuid4())  # type: ignore[arg-type]

        errors = [m for m in ws.sent if m["type"] == "error"]
        assert len(errors) == 1
        assert "empty" in errors[0]["message"].lower()

    async def test_end_session_closes_websocket(self) -> None:
        """end_session message closes the WebSocket."""
        handler, *_ = _make_handler()
        ws = MockWebSocket()

        await ws.enqueue_end_session()

        await handler.handle(ws, uuid4(), str(uuid4()), uuid4())  # type: ignore[arg-type]
        assert ws._closed


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

        await handler.handle(ws, uuid4(), str(uuid4()), uuid4())  # type: ignore[arg-type]

        # Verify gateway.stream was called with WRITE intent
        gateway.stream.assert_called_once()
        call_kwargs = gateway.stream.call_args
        assert call_kwargs.kwargs["intent"].value == "write"

    async def test_interview_uses_chat_intent(self) -> None:
        """interview_assisted mode uses LLMIntent.CHAT and mode='interview'."""
        handler, _, gateway, _ = _make_handler(mode="interview_assisted")
        ws = MockWebSocket()

        await ws.enqueue({"type": "user_direction", "content": "A dog dancing tango"})
        await ws.enqueue_end_session()

        await handler.handle(ws, uuid4(), str(uuid4()), uuid4())  # type: ignore[arg-type]

        # Verify gateway.stream was called with CHAT intent
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

        await handler.handle(ws, uuid4(), str(uuid4()), uuid4())  # type: ignore[arg-type]

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

        await handler.handle(ws, uuid4(), str(uuid4()), uuid4())  # type: ignore[arg-type]

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

        await handler.handle(ws, uuid4(), str(uuid4()), uuid4())  # type: ignore[arg-type]

        # Should have greeting, text_chunk(s), text_done from direction,
        # then text_chunk(s), draft_done from generate_draft
        draft_done = [m for m in ws.sent if m["type"] == "draft_done"]
        assert len(draft_done) == 1
        assert draft_done[0]["word_count"] > 0

    async def test_generate_draft_uses_write_intent(self) -> None:
        """generate_draft calls LLM with WRITE intent and new_chapter mode."""
        handler, _, gateway, _ = _make_handler(mode="interview_assisted")
        gateway.stream = Mock(side_effect=_fake_stream_hello)
        ws = MockWebSocket()

        # First: one interview exchange
        await ws.enqueue({"type": "user_direction", "content": "A mystery novel"})
        # Then: generate draft
        await ws.enqueue({"type": "generate_draft"})
        await ws.enqueue_end_session()

        await handler.handle(ws, uuid4(), str(uuid4()), uuid4())  # type: ignore[arg-type]

        # gateway.stream called twice:
        # 1st: CHAT for interview question
        # 2nd: WRITE for draft generation
        assert gateway.stream.call_count == 2
        draft_call = gateway.stream.call_args_list[1]
        assert draft_call.kwargs["intent"].value == "write"
