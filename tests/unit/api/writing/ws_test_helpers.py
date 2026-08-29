"""Shared helpers for WebSocket writing-session unit tests.

Hosts the mock WebSocket, fake composer, stream fakes, config builder, and
the ``_make_handler`` wiring shared by the writing-session handler tests.
Keeping the helpers here (instead of in each test module) keeps those
modules under the RULE-04 size limit and avoids duplicating fixtures.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock
from uuid import UUID

from fastapi import WebSocketDisconnect

from narrare.auth import ws_tickets
from narrare.writing._ws_cache import InMemorySessionCache
from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
from narrare.writing.ws_factory import build_writing_session_handler
from narrare.writing.ws_session_control_service import WritingSessionControlService
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.writing.session_manager import SessionManager
from narrare_core.writing.session_turn_state import SessionTurnStateStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.writing.ws_handler import WritingSessionHandler
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.context import PromptContext


async def wait_for_gateway_calls(gateway: Mock, expected: int) -> None:
    """Wait until decoupled streaming tasks reach the model registry."""
    for _ in range(50):
        if gateway.stream.call_count >= expected:
            return
        await asyncio.sleep(0.02)
    assert gateway.stream.call_count >= expected


def mint_ws_ticket(user_id: UUID | str) -> str:
    """Mint a single-use WS handshake ticket bound to ``user_id`` (ADR-084).

    Registry-direct mint for tests: every connect/reconnect needs a FRESH
    ticket (single-use — a replayed one is rejected with 4401).
    """
    bound = user_id if isinstance(user_id, UUID) else UUID(user_id)
    return ws_tickets.issue(bound)


def stream_kwargs_for_intent(gateway: Mock, intent_value: str) -> dict[str, Any]:
    """Return kwargs for the first model-registry stream call by intent."""
    for call in gateway.stream.call_args_list:
        if call.kwargs["intent"].value == intent_value:
            return dict(call.kwargs)
    raise AssertionError(f"No stream call for intent {intent_value!r}")


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
    """Create a WritingSessionHandler with mock dependencies.

    Wires a real (no-op) InvocationPipeline and DefaultRunLimitResolver
    so the full invocation contract runs for draft generation (ADR-045).
    The handler constructs WritingTurnService internally from these deps,
    so direction handling also runs the invocation contract.
    """
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    active_turn_registry = ActiveTurnRegistry()
    turn_state = SessionTurnStateStore()
    control_service = WritingSessionControlService(
        session_manager=session_manager,
        turn_state=turn_state,
        registry=active_turn_registry,
    )
    model_registry = Mock()
    # Use Mock (not AsyncMock) for stream — code does `async for` directly
    model_registry.stream = Mock(side_effect=_fake_stream_hello)
    composer = _FakeComposer()
    config = _make_config()
    handler = build_writing_session_handler(
        session_manager=session_manager,
        registry=active_turn_registry,
        turn_state=turn_state,
        control_service=control_service,
        model_registry=model_registry,
        composer=cast("PromptComposer", composer),
        config=config,
        invocation_pipeline=InvocationPipeline(),
        run_limit_resolver=DefaultRunLimitResolver(),
        mode=mode,
    )
    return handler, session_manager, model_registry, composer
