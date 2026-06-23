"""Tests for ActiveTurnRegistry and SessionTransportSink (ADR-052 Phase 1).

Covers:
1. ``SessionTransportSink`` Protocol satisfaction (runtime_checkable).
2. ``register`` / ``get`` / ``get_sink`` store and retrieve turns.
3. ``cancel`` pops the turn, calls ``task.cancel()``, returns
   ``CancelResult(cancelled=True, ...)``.
4. ``cancel`` with no active turn returns ``CancelResult(cancelled=False, ...)``.
5. ``unregister`` removes a completed turn without cancelling.
6. ``rebind_sink`` swaps the sink for an active turn.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from narrare.writing.ws_active_turn_registry import (
    ActiveTurn,
    ActiveTurnRegistry,
    CancelResult,
    NullSessionTransportSink,
    SessionTransportSink,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class RecordingSink:
    """A sink that records sent messages for assertions."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: Mapping[str, object]) -> None:
        self.sent.append(dict(data))


# ---------------------------------------------------------------------------
# Protocol satisfaction
# ---------------------------------------------------------------------------


class TestProtocolSatisfaction:
    """SessionTransportSink Protocol is runtime-checkable."""

    def test_recording_sink_satisfies_protocol(self) -> None:
        assert isinstance(RecordingSink(), SessionTransportSink)

    def test_null_sink_satisfies_protocol(self) -> None:
        assert isinstance(NullSessionTransportSink(), SessionTransportSink)

    def test_object_without_send_json_does_not_satisfy(self) -> None:
        assert not isinstance(object(), SessionTransportSink)


class TestNullSessionTransportSink:
    """NullSessionTransportSink discards sends silently."""

    async def test_send_json_does_not_raise(self) -> None:
        sink = NullSessionTransportSink()
        await sink.send_json({"type": "test"})  # should not raise


# ---------------------------------------------------------------------------
# register / get / get_sink
# ---------------------------------------------------------------------------


class TestRegisterAndGet:
    """register stores the turn; get returns it with task and sink."""

    async def test_register_then_get_returns_turn(self) -> None:
        registry = ActiveTurnRegistry()

        async def _sleep_forever() -> str | None:
            await asyncio.sleep(100)
            return None

        task = asyncio.ensure_future(_sleep_forever())
        sink = RecordingSink()
        try:
            registry.register("s-1", "inv-1", task=task, sink=sink)

            turn = registry.get("s-1")
            assert turn is not None
            assert isinstance(turn, ActiveTurn)
            assert turn.invocation_id == "inv-1"
            assert turn.task is task
            assert turn.sink is sink
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_get_returns_none_when_no_turn(self) -> None:
        registry = ActiveTurnRegistry()
        assert registry.get("ghost") is None

    async def test_get_sink_returns_stored_sink(self) -> None:
        registry = ActiveTurnRegistry()

        async def _noop() -> str | None:
            return None

        task = asyncio.ensure_future(_noop())
        sink = RecordingSink()
        try:
            registry.register("s-1", "inv-1", task=task, sink=sink)
            assert registry.get_sink("s-1") is sink
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_get_sink_returns_null_when_no_turn(self) -> None:
        registry = ActiveTurnRegistry()
        sink = registry.get_sink("ghost")
        assert isinstance(sink, NullSessionTransportSink)


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------


class TestCancel:
    """cancel pops the turn and cancels the underlying task."""

    async def test_cancel_with_active_turn_cancels_task(self) -> None:
        """cancel() calls task.cancel(); CancelledError propagates into the task."""
        registry = ActiveTurnRegistry()
        cancelled_event = asyncio.Event()

        async def _cancellable_task() -> str | None:
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                cancelled_event.set()
                raise
            return None

        task = asyncio.ensure_future(_cancellable_task())
        await asyncio.sleep(0)  # let the task start and reach the await point
        sink = RecordingSink()
        registry.register("s-1", "inv-1", task=task, sink=sink)

        result = registry.cancel("s-1", partial_prose="partial text")

        assert isinstance(result, CancelResult)
        assert result.cancelled is True
        assert result.partial_prose == "partial text"

        # Wait for the task to actually receive the cancellation
        await asyncio.wait_for(cancelled_event.wait(), timeout=2.0)

        # Turn is removed from registry
        assert registry.get("s-1") is None

    async def test_cancel_with_no_active_turn_returns_not_cancelled(self) -> None:
        registry = ActiveTurnRegistry()
        result = registry.cancel("ghost", partial_prose="text")
        assert result.cancelled is False
        assert result.partial_prose == ""


# ---------------------------------------------------------------------------
# unregister
# ---------------------------------------------------------------------------


class TestUnregister:
    """unregister removes a completed turn without cancelling it."""

    async def test_unregister_removes_without_cancelling(self) -> None:
        registry = ActiveTurnRegistry()

        async def _completes_normally() -> str | None:
            return "done"

        task = asyncio.ensure_future(_completes_normally())
        await task  # let it complete

        sink = RecordingSink()
        registry.register("s-1", "inv-1", task=task, sink=sink)

        registry.unregister("s-1")

        assert registry.get("s-1") is None
        # Task should NOT have been cancelled — it already completed
        assert not task.cancelled()


# ---------------------------------------------------------------------------
# rebind_sink
# ---------------------------------------------------------------------------


class TestRebindSink:
    """rebind_sink swaps the sink for an active turn (ADR-052 Phase 2)."""

    async def test_rebind_sink_replaces_sink(self) -> None:
        registry = ActiveTurnRegistry()

        async def _sleep_forever() -> str | None:
            await asyncio.sleep(100)
            return None

        task = asyncio.ensure_future(_sleep_forever())
        old_sink = RecordingSink()
        new_sink = RecordingSink()
        try:
            registry.register("s-1", "inv-1", task=task, sink=old_sink)

            assert registry.rebind_sink("s-1", new_sink) is True
            assert registry.get_sink("s-1") is new_sink
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_rebind_sink_returns_false_when_no_turn(self) -> None:
        registry = ActiveTurnRegistry()
        assert registry.rebind_sink("ghost", RecordingSink()) is False
