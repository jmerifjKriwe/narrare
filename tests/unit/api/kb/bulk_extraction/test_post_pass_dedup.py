"""Corpus post-pass dedup trigger (F3 T3, spec §6.2, D15a).

Covers the kind-gated completion hook: a ``corpus`` job fires exactly ONE
deterministic post-pass ADR-085 analysis (novel + owner passed through,
count → ``mark_dedup``), explicit jobs never trigger, a hook failure is
visible (``corpus_post_pass_dedup_failed`` warning) and non-fatal (the job
stays completed, the dedup block degrades to ``analyzed: false`` — RULE-11),
a shutdown drain cancellation skips the trigger entirely, and the real hook
builds its OWN session and calls ``analyze(..., refresh=True)`` (no stale
cache read — the post-pass must see the pass's just-recorded state).

Fakes reuse ``_runner_fakes.py`` (the F2 runner seams); the hook seam
(``runner._run_post_pass_analysis``) and the analyzer-construction seam
(``runner._analyzer_factory``) are monkeypatched as module attributes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from structlog.testing import capture_logs

from narrare.kb.bulk_extraction import registry, runner
from narrare.kb.bulk_extraction.schemas import BulkJobStatus
from tests.unit.api.kb.bulk_extraction._runner_fakes import (
    NOVEL_ID,
    OWNER,
    _FakeSessions,
    _make_job,
    _noop_pacer,
    _output,
    _RecordingRegistry,
    _ref,
    _ScriptedServiceFactory,
)

if TYPE_CHECKING:
    from uuid import UUID


def _make_corpus_job(*positions: int) -> tuple[str, list[UUID]]:
    """Create a real registry job of kind ``corpus``; return (job_id, ids)."""
    job_id = registry.create(NOVEL_ID, OWNER, [_ref(p) for p in positions], kind="corpus").job_id
    ids = [c.chapter_id for c in registry.status(job_id, OWNER).chapters]
    return job_id, ids


def _hook_recorder(
    monkeypatch: pytest.MonkeyPatch,
    outcome: tuple[bool, int | None] | BaseException,
) -> list[tuple[UUID, UUID]]:
    """Inject a fake ``_run_post_pass_analysis``; return its call log."""
    calls: list[tuple[UUID, UUID]] = []

    async def fake_hook(novel_id: UUID, owner_id: UUID) -> tuple[bool, int | None]:
        calls.append((novel_id, owner_id))
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(runner, "_run_post_pass_analysis", fake_hook)
    return calls


@pytest.fixture(autouse=True)
def _clean_state() -> object:
    """Registry + in-flight set + analyzer seam are process-global — reset."""
    registry._JOBS.clear()
    runner._INFLIGHT_TASKS.clear()
    runner._pacer_acquire = None  # re-arm the lazy defaults for every test
    runner._analyzer_factory = None
    yield
    for task in list(runner._INFLIGHT_TASKS):
        task.cancel()
    runner._INFLIGHT_TASKS.clear()
    registry._JOBS.clear()


class TestKindGate:
    async def test_corpus_completion_triggers_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        job_id, ids = _make_corpus_job(0, 1)
        recorder = _RecordingRegistry()
        hook_calls = _hook_recorder(monkeypatch, (True, 7))
        monkeypatch.setattr(runner, "registry", recorder)
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(
            runner,
            "_service_factory",
            _ScriptedServiceFactory({ids[0]: _output(2), ids[1]: _output(3)}),
        )

        await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        # Exactly ONE post-pass call, novel + owner passed through verbatim.
        assert hook_calls == [(NOVEL_ID, OWNER)]
        assert recorder.calls[-2:] == ["mark_job_completed", "mark_dedup"]
        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.COMPLETED  # the pass itself succeeded
        assert job.dedup is not None
        assert (job.dedup.analyzed, job.dedup.suggestion_count) == (True, 7)

    async def test_explicit_jobs_never_trigger(self, monkeypatch: pytest.MonkeyPatch) -> None:
        job_id, ids = _make_job(0, 1)  # kind defaults to "explicit"
        recorder = _RecordingRegistry()
        hook_calls = _hook_recorder(monkeypatch, (True, 7))
        monkeypatch.setattr(runner, "registry", recorder)
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(
            runner, "_service_factory", _ScriptedServiceFactory({ids[0]: _output(1)})
        )

        await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        assert hook_calls == []
        assert "mark_dedup" not in recorder.calls
        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.COMPLETED
        assert job.dedup is None  # invariant 3: explicit jobs carry no dedup block


class TestHookFailure:
    async def test_hook_failure_is_visible_not_fatal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        job_id, ids = _make_corpus_job(0, 1)
        recorder = _RecordingRegistry()
        _hook_recorder(monkeypatch, RuntimeError("resolution analysis down"))
        monkeypatch.setattr(runner, "registry", recorder)
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(
            runner,
            "_service_factory",
            _ScriptedServiceFactory({ids[0]: _output(1), ids[1]: _output(1)}),
        )

        with capture_logs() as logs:
            await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        warnings = [e for e in logs if e["event"] == "corpus_post_pass_dedup_failed"]
        assert len(warnings) == 1
        assert warnings[0]["job_id"] == job_id
        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.COMPLETED  # non-fatal (RULE-11)
        assert job.dedup is not None
        assert (job.dedup.analyzed, job.dedup.suggestion_count) == (False, None)
        assert recorder.calls[-2:] == ["mark_job_completed", "mark_dedup_unavailable"]


class TestDrainCancellation:
    async def test_shutdown_cancel_skips_trigger(self, monkeypatch: pytest.MonkeyPatch) -> None:
        job_id, ids = _make_corpus_job(0, 1)
        recorder = _RecordingRegistry()
        hook_calls = _hook_recorder(monkeypatch, (True, 7))
        monkeypatch.setattr(runner, "registry", recorder)
        monkeypatch.setattr(runner, "_pacer_acquire", _noop_pacer)
        monkeypatch.setattr(
            runner,
            "_service_factory",
            _ScriptedServiceFactory({ids[0]: asyncio.CancelledError()}),
        )

        with pytest.raises(asyncio.CancelledError):
            await runner.run_bulk_extraction(job_id, NOVEL_ID, OWNER)

        assert hook_calls == []  # drain wins — a shutdown-cancelled job never triggers
        assert "mark_dedup" not in recorder.calls
        job = registry.status(job_id, OWNER)
        assert job.dedup is not None
        assert (job.dedup.analyzed, job.dedup.suggestion_count) == (
            False,
            None,
        )  # dedup block untouched at its default


@dataclass
class _FakeAnalysisResponse:
    """Value stand-in for ``ResolutionAnalysisResponse`` (len only)."""

    suggestions: list[object] = field(default_factory=list)


class _FakeAnalyzer:
    """Records the ``analyze`` contract the real post-pass must honor."""

    def __init__(self, calls: list[tuple[UUID, UUID, bool]]) -> None:
        self._calls = calls

    async def analyze(
        self, novel_id: UUID, user_id: UUID, *, refresh: bool = False
    ) -> _FakeAnalysisResponse:
        self._calls.append((novel_id, user_id, refresh))
        return _FakeAnalysisResponse(suggestions=[object() for _ in range(7)])


class TestRealHook:
    async def test_real_hook_builds_own_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sessions = _FakeSessions()
        built_with: list[object] = []
        analyze_calls: list[tuple[UUID, UUID, bool]] = []

        def fake_analyzer_factory(session: object) -> _FakeAnalyzer:
            built_with.append(session)
            return _FakeAnalyzer(analyze_calls)

        monkeypatch.setattr("narrare._app.database.get_session_factory", lambda: sessions)
        monkeypatch.setattr(runner, "_analyzer_factory", fake_analyzer_factory)

        result = await runner._run_post_pass_analysis(NOVEL_ID, OWNER)

        assert result == (True, 7)
        assert len(sessions.entered) == 1  # ONE own session — no request session
        assert sessions.closed == sessions.entered  # opened and closed
        assert built_with == sessions.entered  # analyzer built ON that session
        assert analyze_calls == [(NOVEL_ID, OWNER, True)]  # refresh=True, no stale cache
