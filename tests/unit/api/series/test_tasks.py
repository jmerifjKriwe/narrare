"""Unit tests for band-summary in-process dispatch (Spec 2 Task 5, ADR-080).

Verifies that ``enqueue_band_summary_generation`` (the production
``BandSummaryEnqueuer``) launches ``generate_band_summary_inprocess`` via
``asyncio.create_task`` fire-and-forget, with a GC-guarded strong reference.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from structlog.testing import capture_logs

from narrare.series import tasks as series_tasks

if TYPE_CHECKING:
    from narrare.series.band_summary_auto_trigger import BandSummaryEnqueuer


class TestEnqueueBandSummaryGeneration:
    """``enqueue_band_summary_generation`` dispatches in-process (ADR-080)."""

    @pytest.mark.asyncio
    async def test_dispatches_inprocess_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The enqueuer schedules generate_band_summary_inprocess via create_task."""
        captured: list = []

        async def fake_inprocess(novel_id: object) -> None:
            captured.append(novel_id)

        monkeypatch.setattr(series_tasks, "generate_band_summary_inprocess", fake_inprocess)

        novel_id = uuid4()
        await series_tasks.enqueue_band_summary_generation(novel_id)

        assert len(series_tasks._INFLIGHT_TASKS) == 1
        task = next(iter(series_tasks._INFLIGHT_TASKS))
        await task

        assert captured == [novel_id]

    @pytest.mark.asyncio
    async def test_gc_guard_removes_completed_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The GC guard discards the task once it completes (ADR-080)."""
        from narrare.series import tasks as st

        async def fake_inprocess(novel_id: object) -> None:
            pass

        monkeypatch.setattr(st, "generate_band_summary_inprocess", fake_inprocess)

        await series_tasks.enqueue_band_summary_generation(uuid4())

        assert len(st._INFLIGHT_TASKS) == 1
        task = next(iter(st._INFLIGHT_TASKS))
        await task
        await asyncio.sleep(0)  # let add_done_callback run

        assert len(st._INFLIGHT_TASKS) == 0

    @pytest.mark.asyncio
    async def test_does_not_await_runner(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The enqueuer is fire-and-forget — returns before the runner finishes."""
        started: list[bool] = []

        async def slow_inprocess(novel_id: object) -> None:
            started.append(True)
            await asyncio.sleep(0.05)

        monkeypatch.setattr(series_tasks, "generate_band_summary_inprocess", slow_inprocess)

        await series_tasks.enqueue_band_summary_generation(uuid4())

        assert len(series_tasks._INFLIGHT_TASKS) == 1
        task = next(iter(series_tasks._INFLIGHT_TASKS))
        await task
        assert started == [True]

    @pytest.mark.asyncio
    async def test_failing_runner_logs_background_task_failed(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failing background task logs via structlog and is retrieved.

        Regression for IMP-1: the done-callback must call ``task.exception()``
        so asyncio does not emit an un-retrieved-exception warning, and the
        failure is surfaced as a structured error event (RULE-11). The GC
        guard must still discard the task.
        """

        async def boom_inprocess(novel_id: object) -> None:
            raise RuntimeError("band-summary boom")

        monkeypatch.setattr(series_tasks, "generate_band_summary_inprocess", boom_inprocess)

        with capture_logs() as logs:
            await series_tasks.enqueue_band_summary_generation(uuid4())

            assert len(series_tasks._INFLIGHT_TASKS) == 1
            task = next(iter(series_tasks._INFLIGHT_TASKS))
            # Wait for completion without re-raising (asyncio.wait never raises
            # — it just returns the done set). Then yield once so the
            # add_done_callback fires.
            await asyncio.wait([task])
            await asyncio.sleep(0)

        failures = [r for r in logs if r.get("event") == "background_task_failed"]
        assert len(failures) == 1, f"expected one error log, got {logs}"
        assert failures[0]["log_level"] == "error"
        assert "band-summary boom" in failures[0]["error"]
        # The GC guard still discards the failed task.
        assert len(series_tasks._INFLIGHT_TASKS) == 0

    def test_signature_matches_band_summary_enqueuer_alias(self) -> None:
        """The enqueuer is assignable to the BandSummaryEnqueuer callable alias.

        This guarantees call-site compatibility with SeriesService DI
        (RULE-07): the DI factory injects this function, unit tests inject a
        recording fake of the same alias type.
        """
        enqueuer: BandSummaryEnqueuer = series_tasks.enqueue_band_summary_generation
        assert callable(enqueuer)
