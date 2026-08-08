"""Unit tests for ``narrare._app.inflight`` — graceful-shutdown task drain.

Covers the cancel-first drain of the module-level ``_INFLIGHT_TASKS``
GC-guard sets (ADR-080 in-process dispatch):

- every in-flight task in both drain sources is cancelled and awaited,
- each cancelled task is logged at **info** (intentional cancellation is
  not an error — RULE-11),
- empty GC-guard sets are a silent no-op (no log, no error),
- exceptions raised by tasks during cancellation never propagate
  (``asyncio.gather(..., return_exceptions=True)``).
"""

from __future__ import annotations

import asyncio

import pytest
from structlog.testing import capture_logs

import narrare.kb.embedding_hooks as embedding_hooks
import narrare.series.tasks as series_tasks
from narrare._app import inflight

_DRAIN_SOURCES = {
    "narrare.kb.embedding_hooks",
    "narrare.series.tasks",
}


async def _never_finish() -> None:
    """Coroutine that blocks until cancelled."""
    await asyncio.sleep(3600)


async def _refuse_cancel() -> None:
    """Coroutine that raises RuntimeError instead of honouring cancellation."""
    try:
        await asyncio.sleep(3600)
    except asyncio.CancelledError:
        raise RuntimeError("task refused to cancel") from None


@pytest.fixture(autouse=True)
def _empty_inflight_sets(  # pyright: ignore[reportUnusedFunction]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Start every drain test from empty GC-guard sets.

    The drain reads the module attributes at call time, so monkeypatching
    the real modules' ``_INFLIGHT_TASKS`` controls exactly what is drained
    (the same mechanism the production drain uses via importlib).
    """
    monkeypatch.setattr(embedding_hooks, "_INFLIGHT_TASKS", set[asyncio.Task[None]]())
    monkeypatch.setattr(series_tasks, "_INFLIGHT_TASKS", set[asyncio.Task[None]]())


class TestDrainInflightTasks:
    """``drain_inflight_tasks`` cancels, awaits, and logs in-flight tasks."""

    @pytest.mark.asyncio
    async def test_cancels_and_awaits_every_tracked_task(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Every task in both GC-guard sets is cancelled and awaited."""
        task_a = asyncio.create_task(_never_finish())
        task_b = asyncio.create_task(_never_finish())
        await asyncio.sleep(0)  # let both coroutines start

        monkeypatch.setattr(embedding_hooks, "_INFLIGHT_TASKS", {task_a})
        monkeypatch.setattr(series_tasks, "_INFLIGHT_TASKS", {task_b})

        with capture_logs() as logs:
            await inflight.drain_inflight_tasks()

        assert task_a.cancelled()
        assert task_b.cancelled()
        assert task_a.done()
        assert task_b.done()

        # Each cancelled task is surfaced at info level with its source.
        events = [r for r in logs if r.get("event") == "background_task_cancelled_shutdown"]
        assert len(events) == 2
        assert all(e.get("log_level") == "info" for e in events)
        assert {e.get("source") for e in events} == _DRAIN_SOURCES
        assert all(e.get("task_name") for e in events)

    @pytest.mark.asyncio
    async def test_cancels_multiple_tasks_from_one_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A source holding several tasks drains all of them."""
        tasks = [asyncio.create_task(_never_finish()) for _ in range(3)]
        await asyncio.sleep(0)

        monkeypatch.setattr(embedding_hooks, "_INFLIGHT_TASKS", set(tasks))

        with capture_logs() as logs:
            await inflight.drain_inflight_tasks()

        assert all(t.cancelled() for t in tasks)
        events = [r for r in logs if r.get("event") == "background_task_cancelled_shutdown"]
        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_empty_sets_are_silent_noop(self) -> None:
        """With no tracked tasks the drain returns without logging (RULE-11)."""
        with capture_logs() as logs:
            await inflight.drain_inflight_tasks()

        assert logs == []

    @pytest.mark.asyncio
    async def test_exceptions_during_cancel_do_not_propagate(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Tasks that raise instead of honouring cancellation are absorbed."""
        task = asyncio.create_task(_refuse_cancel())
        await asyncio.sleep(0)

        monkeypatch.setattr(embedding_hooks, "_INFLIGHT_TASKS", {task})

        # Must not raise — return_exceptions=True absorbs the RuntimeError.
        with capture_logs():
            await inflight.drain_inflight_tasks()

        assert task.done()
        assert isinstance(task.exception(), RuntimeError)

    @pytest.mark.asyncio
    async def test_cancelled_task_is_not_logged_as_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Intentional shutdown cancellation is never surfaced as an error.

        Regression guard for RULE-11: the drain must log at info only and
        never emit a ``background_task_failed`` error for a cancelled task.
        """
        task = asyncio.create_task(_never_finish())
        await asyncio.sleep(0)
        monkeypatch.setattr(series_tasks, "_INFLIGHT_TASKS", {task})

        with capture_logs() as logs:
            await inflight.drain_inflight_tasks()

        assert task.cancelled()
        assert [r for r in logs if r.get("event") == "background_task_failed"] == []
