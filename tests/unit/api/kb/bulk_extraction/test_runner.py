"""Runner semantics for the bulk extraction job (F2 T3, ADR-092 §5).

Covers: the per-chapter state walk, per-chapter failure isolation, the
ConfigurationError fast-fail, cooperative cancel between chapters, one
pacer acquire per attempted chapter, the OWN-session-per-chapter rule
(fake session factory capturing each chapter's session), CancelledError
propagation (drain), the done-callback shutdown flip, dispatch tracking
(GC guard), and the outer infrastructure guard that can never leave a
job hung in RUNNING (RULE-11).

Fakes live in ``_runner_fakes.py`` (RULE-04 split); they are monkeypatched
onto the runner's module-attribute seams.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from narrare.kb.bulk_extraction import registry, runner
from narrare.kb.bulk_extraction.schemas import BulkChapterState, BulkJobStatus
from narrare_core.shared.errors import ConfigurationError
from tests.unit.api.kb.bulk_extraction._runner_fakes import (
    _BLOCK,
    NOVEL_ID,
    OWNER,
    _FakeSessions,
    _make_job,
    _noop_pacer,
    _output,
    _RecordingRegistry,
    _ScriptedServiceFactory,
    _wait_until,
)

if TYPE_CHECKING:
    from uuid import UUID


@pytest.fixture(autouse=True)
def _clean_state() -> object:
    """Registry + in-flight set are process-global — start every test empty."""
    registry._JOBS.clear()
    runner._INFLIGHT_TASKS.clear()
    runner._pacer_acquire = None  # re-arm the lazy default for every test
    yield
    for task in list(runner._INFLIGHT_TASKS):
        task.cancel()
    runner._INFLIGHT_TASKS.clear()
    registry._JOBS.clear()


class TestStateWalk:
    async def test_two_successful_chapters_walk_and_complete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        job_id, ids = _make_job(0, 1)
        recorder = _RecordingRegistry()
        monkeypatch.setattr(runner, "registry", recorder)
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(
            runner,
            "_service_factory",
            _ScriptedServiceFactory({ids[0]: _output(3), ids[1]: _output(1)}),
        )

        await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        assert recorder.calls == [
            "mark_job_running",
            "mark_chapter_running",
            "mark_chapter_done",
            "mark_chapter_running",
            "mark_chapter_done",
            "mark_job_completed",
        ]
        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.COMPLETED
        assert (job.totals.total, job.totals.done, job.totals.failed, job.totals.remaining) == (
            2,
            2,
            0,
            0,
        )
        rows = job.chapters
        assert [row.state for row in rows] == [BulkChapterState.DONE, BulkChapterState.DONE]
        assert [row.item_count for row in rows] == [3, 1]


class TestFailureIsolation:
    async def test_chapter_failure_records_error_and_job_continues(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        job_id, ids = _make_job(0, 1)
        monkeypatch.setattr(runner, "registry", _RecordingRegistry())
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(
            runner,
            "_service_factory",
            _ScriptedServiceFactory({ids[0]: RuntimeError("agent exploded"), ids[1]: _output(2)}),
        )

        await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.COMPLETED  # isolated chapter failure ≠ job failure
        assert (job.totals.failed, job.totals.done, job.totals.remaining) == (1, 1, 0)
        rows = job.chapters
        assert rows[0].state is BulkChapterState.FAILED
        assert rows[0].error == "agent exploded"
        assert rows[0].item_count is None
        assert rows[1].state is BulkChapterState.DONE


class TestConfigurationFastFail:
    async def test_configuration_error_fails_job_and_skips_rest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        job_id, ids = _make_job(0, 1)
        factory = _ScriptedServiceFactory(
            {ids[0]: ConfigurationError("NO_AI_PROVIDER"), ids[1]: _output(1)}
        )
        monkeypatch.setattr(runner, "registry", _RecordingRegistry())
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(runner, "_service_factory", factory)

        await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.FAILED
        assert job.error == "NO_AI_PROVIDER"
        assert [chapter_id for chapter_id, _ in factory.extract_calls] == [ids[0]]
        assert job.chapters[1].state is BulkChapterState.PENDING  # never attempted


class TestCooperativeCancel:
    async def test_cancel_between_chapters_keeps_done_and_pends_rest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        job_id, ids = _make_job(0, 1)
        factory = _ScriptedServiceFactory({ids[0]: _output(1), ids[1]: _output(1)})

        def cancel_after_first(_chapter_id: UUID) -> None:
            registry.request_cancel(job_id, OWNER)  # flag set while chapter 1 is in flight

        factory.on_extract = cancel_after_first
        monkeypatch.setattr(runner, "registry", _RecordingRegistry())
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(runner, "_service_factory", factory)

        await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.CANCELLED
        assert job.error == "cancelled by user"
        assert job.chapters[0].state is BulkChapterState.DONE  # in-flight chapter recorded
        assert job.chapters[1].state is BulkChapterState.PENDING


class TestPacing:
    async def test_pacer_acquired_exactly_once_per_attempted_chapter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        job_id, ids = _make_job(0, 1)
        calls = 0

        async def counting_pacer() -> None:
            nonlocal calls
            calls += 1

        monkeypatch.setattr(runner, "registry", _RecordingRegistry())
        monkeypatch.setattr(runner, "_pacer_acquire", counting_pacer)
        monkeypatch.setattr(
            runner,
            "_service_factory",
            _ScriptedServiceFactory({ids[0]: _output(1), ids[1]: _output(1)}),
        )

        await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)
        assert calls == 2


class TestSessionHygiene:
    async def test_own_session_per_chapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        job_id, ids = _make_job(0, 1)
        sessions = _FakeSessions()
        factory = _ScriptedServiceFactory({ids[0]: _output(1), ids[1]: _output(1)})
        monkeypatch.setattr(runner, "registry", _RecordingRegistry())
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(runner, "_service_factory", factory)
        monkeypatch.setattr("narrare._app.database.get_session_factory", lambda: sessions)

        await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        # One OWN session per chapter — opened and closed, never shared.
        assert sessions.open_calls == 2
        assert len(sessions.entered) == 2
        assert sessions.entered[0] is not sessions.entered[1]
        assert sessions.closed == sessions.entered  # every session was closed
        # Each chapter's service was built on its own session.
        assert [session for _, session in factory.extract_calls] == sessions.entered


class TestDrainCancellation:
    async def test_cancelled_error_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        job_id, ids = _make_job(0, 1)
        recorder = _RecordingRegistry()
        monkeypatch.setattr(runner, "registry", recorder)
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(
            runner, "_service_factory", _ScriptedServiceFactory({ids[0]: asyncio.CancelledError()})
        )

        with pytest.raises(asyncio.CancelledError):
            await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        # Not swallowed into a terminal state — the drain done-callback owns that.
        assert "mark_job_completed" not in recorder.calls
        assert "mark_job_failed" not in recorder.calls
        assert registry.status(job_id, OWNER).status is BulkJobStatus.RUNNING

    async def test_on_done_marks_shutdown_cancelled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        job_id, ids = _make_job(0)
        started = asyncio.Event()
        factory = _ScriptedServiceFactory({ids[0]: _BLOCK})

        def signal_started(_chapter_id: UUID) -> None:
            started.set()

        factory.on_extract = signal_started
        monkeypatch.setattr(runner, "registry", _RecordingRegistry())
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(runner, "_service_factory", factory)

        await runner.dispatch(job_id, NOVEL_ID, OWNER)
        (task,) = runner._INFLIGHT_TASKS
        assert task.get_name() == job_id
        await asyncio.wait_for(started.wait(), timeout=2)

        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.CANCELLED
        assert job.error == "cancelled (server shutdown)"
        assert job_id not in runner._INFLIGHT_TASKS  # GC-guard discard ran

    async def test_dispatch_tracks_task_and_cleans_up(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        job_id, ids = _make_job(0)
        monkeypatch.setattr(runner, "registry", _RecordingRegistry())
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(
            runner, "_service_factory", _ScriptedServiceFactory({ids[0]: _output(4)})
        )

        await runner.dispatch(job_id, NOVEL_ID, OWNER)
        assert len(runner._INFLIGHT_TASKS) == 1
        await _wait_until(lambda: not runner._INFLIGHT_TASKS)

        assert registry.status(job_id, OWNER).status is BulkJobStatus.COMPLETED
        assert not runner._INFLIGHT_TASKS


class TestInfrastructureGuard:
    async def test_pacer_failure_fails_job_instead_of_hanging_running(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        job_id, ids = _make_job(0)

        async def broken_pacer() -> None:
            raise RuntimeError("pacer down")

        recorder = _RecordingRegistry()
        monkeypatch.setattr(runner, "registry", recorder)
        monkeypatch.setattr(runner, "_pacer_acquire", broken_pacer)
        monkeypatch.setattr(
            runner, "_service_factory", _ScriptedServiceFactory({ids[0]: _output(1)})
        )

        await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.FAILED  # never a hung RUNNING job (RULE-11)
        assert "RuntimeError" in (job.error or "")
        assert "mark_chapter_running" not in recorder.calls
