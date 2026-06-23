"""Tests for WritingDirectionDispatcher decoupled streaming (ADR-052 Phase 1).

Covers:
1. ``dispatch`` spawns a background streaming task, registers it in the
   :class:`ActiveTurnRegistry`, records chunks into
   :class:`SessionTurnStateStore`, and returns the ``invocation_id``.
2. ``dispatch`` rejects a second concurrent ``user_direction`` with a
   ``busy`` error and does NOT register a second task.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from uuid import UUID

from narrare.writing._ws_cache import InMemorySessionCache
from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
from narrare.writing.ws_direction_dispatch import WritingDirectionDispatcher
from narrare.writing.ws_session_context import WritingSessionContext
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.writing.session_manager import SessionManager
from narrare_core.writing.session_turn_state import SessionTurnStateStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _RecordingSocket:
    """Minimal WebSocket-like that records sent messages."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: Mapping[str, object]) -> None:
        self.sent.append(dict(data))


class _FakeTurnService:
    """A turn service whose stream_turn yields chunks then blocks.

    Yields two text chunks then sleeps forever (so the test can inspect
    mid-stream state and the task can be cancelled on cleanup).
    """

    def __init__(self) -> None:
        self.chunks_yielded = 0

    async def stream_turn(
        self,
        *,
        content: str,
        session_mode: str,
        user_id: object,
        project_id: object,
        chapter_id: object,
        session_id: object,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(text="Hello ")
        self.chunks_yielded += 1
        yield StreamChunk(text="world!")
        self.chunks_yielded += 1
        # Block forever — simulates a slow LLM provider mid-stream
        await asyncio.sleep(100)
        yield StreamChunk(text="", is_final=True, usage=TokenUsage(10, 20, 30))


class _ControlledTurnService:
    """A turn service that waits before yielding, enabling sink rebinding."""

    def __init__(self) -> None:
        self.release = asyncio.Event()

    async def stream_turn(
        self,
        *,
        content: str,
        session_mode: str,
        user_id: object,
        project_id: object,
        chapter_id: object,
        session_id: object,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        await self.release.wait()
        yield StreamChunk(text="rebound chunk")
        await asyncio.sleep(100)


def _make_dispatcher() -> tuple[
    WritingDirectionDispatcher,
    SessionManager,
    SessionTurnStateStore,
    ActiveTurnRegistry,
    _FakeTurnService,
]:
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    turn_state = SessionTurnStateStore()
    registry = ActiveTurnRegistry()
    turn_service = _FakeTurnService()
    dispatcher = WritingDirectionDispatcher(
        session_manager=session_manager,
        turn_state=turn_state,
        registry=registry,
        turn_service=turn_service,  # type: ignore[arg-type]
        api_key=None,
        base_url=None,
    )
    return dispatcher, session_manager, turn_state, registry, turn_service


async def _make_context(session_manager: SessionManager) -> WritingSessionContext:
    from uuid import uuid4

    chapter_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()
    session_id = await session_manager.create_session(
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
    )
    return WritingSessionContext(
        session_id=session_id,
        user_id=user_id,
        project_id=project_id,
        chapter_id=chapter_id,
        mode="interactive_session",
    )


def _cancel(turn_registry: ActiveTurnRegistry, session_id_str: str) -> asyncio.Task[str | None]:
    """Cancel and return the background task for cleanup."""
    turn = turn_registry.get(session_id_str)
    assert turn is not None
    task = turn.task
    task.cancel()
    return task


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDispatchRegistersAndStreams:
    """dispatch spawns a decoupled streaming task."""

    async def test_dispatch_registers_active_turn_and_returns_invocation_id(
        self,
    ) -> None:
        dispatcher, session_manager, turn_state, registry, _ = _make_dispatcher()
        context = await _make_context(session_manager)
        ws = _RecordingSocket()
        session_id_str = str(context.session_id)

        invocation_id = await dispatcher.dispatch(
            ws,  # type: ignore[arg-type]
            context,
            "Write a scene",
        )

        assert invocation_id is not None
        assert isinstance(invocation_id, UUID)

        # Registry has the active turn
        turn = registry.get(session_id_str)
        assert turn is not None
        assert turn.invocation_id == str(invocation_id)

        # Give the task time to yield chunks
        await asyncio.sleep(0.1)

        # Turn state has partial prose from the yielded chunks
        partial = await turn_state.get_active_partial(session_id_str)
        assert "Hello" in partial
        assert "world" in partial

        # Cleanup: cancel the background task
        task = _cancel(registry, session_id_str)
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def test_rebound_sink_receives_subsequent_stream_chunks(self) -> None:
        """After reattach, the streaming task sends via the rebound sink."""
        cache = InMemorySessionCache()
        session_manager = SessionManager(cache=cache)
        turn_state = SessionTurnStateStore()
        registry = ActiveTurnRegistry()
        turn_service = _ControlledTurnService()
        dispatcher = WritingDirectionDispatcher(
            session_manager=session_manager,
            turn_state=turn_state,
            registry=registry,
            turn_service=turn_service,  # type: ignore[arg-type]
        )
        context = await _make_context(session_manager)
        original_ws = _RecordingSocket()
        rebound_sink = _RecordingSocket()
        session_id_str = str(context.session_id)

        invocation_id = await dispatcher.dispatch(
            original_ws,  # type: ignore[arg-type]
            context,
            "Write a scene",
        )
        assert invocation_id is not None
        assert registry.rebind_sink(session_id_str, rebound_sink) is True

        turn_service.release.set()
        await asyncio.sleep(0.1)

        assert {m.get("text") for m in rebound_sink.sent} == {"rebound chunk"}
        assert all(m.get("text") != "rebound chunk" for m in original_ws.sent)

        task = _cancel(registry, session_id_str)
        with contextlib.suppress(asyncio.CancelledError):
            await task

    async def test_dispatch_rejects_concurrent_direction_with_busy_error(
        self,
    ) -> None:
        dispatcher, session_manager, _, registry, _ = _make_dispatcher()
        context = await _make_context(session_manager)
        ws = _RecordingSocket()
        session_id_str = str(context.session_id)

        # First dispatch — spawns streaming task
        first_id = await dispatcher.dispatch(
            ws,  # type: ignore[arg-type]
            context,
            "Write a scene",
        )
        assert first_id is not None

        # Second dispatch — should be rejected
        second_id = await dispatcher.dispatch(
            ws,  # type: ignore[arg-type]
            context,
            "Write another scene",
        )

        assert second_id is None

        # An error message was sent mentioning "already"
        busy_errors = [
            m
            for m in ws.sent
            if m.get("type") == "error" and "already" in str(m.get("message", "")).lower()
        ]
        assert len(busy_errors) >= 1

        # Registry still has only the first turn
        turn = registry.get(session_id_str)
        assert turn is not None
        assert turn.invocation_id == str(first_id)

        # Cleanup
        task = _cancel(registry, session_id_str)
        with contextlib.suppress(asyncio.CancelledError):
            await task
