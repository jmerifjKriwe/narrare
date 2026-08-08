"""Regression tests: end_session during streaming (PR #157 review follow-up).

Verified bug: the ``end_session`` eviction (``ws_message_router.py`` →
``session_manager.end_session`` → ``cache.delete``) runs while the decoupled
stream task is still streaming. On SUCCESS the task calls ``add_message`` —
outside the ``try/except`` in ``_run_stream`` — which raises
``ValueError('Session ... not found or expired.')`` from ``_load_or_raise``.
Nothing retrieves the exception (``Task exception was never retrieved``) and
``ActiveTurnRegistry.unregister`` never runs → registry leak.

Approved fix (architecture decision):
1. Exception-safe success tail in ``_run_stream``: ``try/finally`` with
   ``unregister`` in ``finally``; ``add_message`` guarded with
   ``except ValueError`` (benign end_session race → info log, ``text_done``
   deliberately skipped).
2. Done-callback at the dispatch site that retrieves any escaped exception
   and unregisters as a last resort.

The fakes are FRESH and module-local (RULE-04 — the stop test file stays at
its size limit; this mirrors its controlled-turn pattern).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import pytest
import structlog

from narrare.writing._ws_cache import InMemorySessionCache
from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
from narrare.writing.ws_direction_dispatch import WritingDirectionDispatcher
from narrare.writing.ws_session_context import WritingSessionContext
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.writing.session_manager import SessionManager
from narrare_core.writing.session_turn_state import SessionTurnStateStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator, Mapping


# ---------------------------------------------------------------------------
# structlog → stdlib bridge (so caplog can capture the dispatcher's events)
# ---------------------------------------------------------------------------


@pytest.fixture
def structlog_stdlib() -> Iterator[None]:
    """Temporarily route structlog through stdlib logging for caplog capture.

    Unit tests never call ``configure_logging()``, so structlog defaults to
    its ``PrintLoggerFactory`` (stdout) and ``caplog`` cannot see any
    structlog events (documented in
    ``tests/integration/test_no_mem0_clients_in_session.py``). This fixture
    reconfigures structlog stdlib-backed for the duration of the test and
    restores the previous config afterwards. Loggers are lazy
    ``BoundLoggerLazyProxy`` objects, so already-created module loggers
    resolve through the current config on each call.
    """
    saved = structlog.get_config()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        cache_logger_on_first_use=False,
    )
    yield
    structlog.configure(**saved)


def _record_event(record: logging.LogRecord) -> str:
    """Extract the structlog event name from a captured record."""
    if isinstance(record.msg, dict):
        return str(record.msg.get("event", ""))
    return str(record.getMessage())


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _RecordingSocket:
    """Minimal WebSocket-like that records sent messages."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: Mapping[str, object]) -> None:
        self.sent.append(dict(data))


class _EndSessionTurnService:
    """A turn service that waits for release, then finishes successfully.

    Yields one text chunk (so ``result.full_text`` is non-empty and the
    success path persists the assistant message) followed by the final
    usage chunk. Mirrors the proven ``_ControlledTurnService`` construction
    pattern from the stop test.
    """

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
        yield StreamChunk(text="final")
        yield StreamChunk(text="", is_final=True, usage=TokenUsage(1, 2, 3))


def _make_dispatcher() -> tuple[
    WritingDirectionDispatcher,
    SessionManager,
    SessionTurnStateStore,
    ActiveTurnRegistry,
    _EndSessionTurnService,
]:
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    turn_state = SessionTurnStateStore()
    registry = ActiveTurnRegistry()
    turn_service = _EndSessionTurnService()
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEndSessionDuringStream:
    """end_session while streaming: benign race, clean teardown."""

    async def test_end_session_during_stream_unregisters_and_drops_transcript(
        self,
        caplog: pytest.LogCaptureFixture,
        structlog_stdlib: None,
    ) -> None:
        dispatcher, session_manager, _, registry, turn_service = _make_dispatcher()
        context = await _make_context(session_manager)
        ws = _RecordingSocket()
        session_id_str = str(context.session_id)

        invocation_id = await dispatcher.dispatch(
            ws,  # type: ignore[arg-type]
            context,
            "Write a scene",
        )
        assert invocation_id is not None

        # Mid-flight: the stream task is registered and blocked on release
        active_turn = registry.get(session_id_str)
        assert active_turn is not None
        task = active_turn.task

        # Reproduce the router branch exactly: end_session evicts the cache
        # while the stream is still running.
        await session_manager.end_session(context.session_id)

        # Release the stream; the success tail now races with the eviction.
        turn_service.release.set()

        # STRONG PIN: awaiting the registered task surfaces the unretrieved
        # exception with the bug (ValueError from add_message) and returns
        # cleanly with the fix.
        caplog.set_level(logging.INFO)
        await asyncio.wait_for(task, timeout=5)

        # unregister must have run (no registry leak)
        assert registry.get(session_id_str) is None

        # benign race logged at info; no error-level task-failure log
        ended = [r for r in caplog.records if _record_event(r) == "direction_stream_session_ended"]
        assert len(ended) == 1
        assert ended[0].levelno == logging.INFO
        failed = [r for r in caplog.records if _record_event(r) == "direction_stream_task_failed"]
        assert failed == []

        # dropped-transcript behavior: no text_done after end_session
        assert all(m.get("type") != "text_done" for m in ws.sent)


class TestDoneCallbackLastResort:
    """The dispatch-site done-callback retrieves exceptions and unregisters."""

    async def test_done_callback_retrieves_exception_and_unregisters_last_resort(
        self,
        caplog: pytest.LogCaptureFixture,
        structlog_stdlib: None,
    ) -> None:
        dispatcher, session_manager, _, registry, _ = _make_dispatcher()
        context = await _make_context(session_manager)
        session_id_str = str(context.session_id)

        async def _boom() -> None:
            raise RuntimeError("boom")

        task = asyncio.ensure_future(_boom())
        registry.register(
            session_id_str,
            "inv-last-resort",
            task=task,
            sink=_RecordingSocket(),
        )

        # Let the task finish with its exception (Task.exception() requires a
        # done task, and the callback is the production retrieval point).
        with pytest.raises(RuntimeError):
            await task

        caplog.set_level(logging.INFO)
        dispatcher._on_stream_done(session_id_str, task)

        # last-resort unregister ran
        assert registry.get(session_id_str) is None

        # unexpected failure logged at error
        failed = [r for r in caplog.records if _record_event(r) == "direction_stream_task_failed"]
        assert len(failed) == 1
        assert failed[0].levelno == logging.ERROR
