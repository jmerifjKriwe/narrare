"""Unit tests for Pydantic Evals runner serialization and drift parsing."""

from __future__ import annotations

import asyncio
import gc
import json
import warnings
from typing import TYPE_CHECKING

import pytest
from evals.datasets import available_suites
from evals.runner import run_suites
from evals.tasks import available_suites_for_mode, get_task
from evals.tasks.runtime import RuntimeTaskFactory
from evals.tasks.smoke import SmokeTaskFactory
from scripts.eval_drift.parser import parse_pydantic_eval_report

if TYPE_CHECKING:
    from pathlib import Path


def _run_suites_safe(*args, **kwargs) -> int:
    """Run ``run_suites`` without destroying the pytest-asyncio session event loop.

    ``pydantic_evals.Dataset.evaluate_sync()`` calls ``asyncio.get_event_loop()``
    which — when called from sync code with the pytest-asyncio session loop set
    in the policy — *reuses* the session loop. The loop-closing cleanup in
    ``run_suites`` must not close the session loop; this helper provides an
    additional safety layer by clearing the session loop from the policy before
    the call and restoring it afterward.
    """
    try:
        saved = asyncio.get_event_loop()
    except RuntimeError:
        saved = None

    asyncio.set_event_loop(None)
    try:
        return run_suites(*args, **kwargs)
    finally:
        if saved is not None and not saved.is_closed():
            asyncio.set_event_loop(saved)


def test_runner_writes_smoke_report(tmp_path: Path) -> None:
    exit_code = _run_suites_safe(
        suite="rewrite_selection",
        mode="smoke",
        results_dir=tmp_path,
        minimum_score=0.8,
        judge_model=None,
    )

    report_path = tmp_path / "rewrite_selection.json"
    assert exit_code == 0
    assert report_path.is_file()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["framework"] == "pydantic-evals"
    assert payload["cases"]


def test_runner_writes_staged_consistency_smoke_report(tmp_path: Path) -> None:
    exit_code = _run_suites_safe(
        suite="consistency_staged",
        mode="smoke",
        results_dir=tmp_path,
        minimum_score=0.8,
        judge_model=None,
    )

    report_path = tmp_path / "consistency_staged.json"
    assert exit_code == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["suite"] == "consistency_staged"
    assert [case["name"] for case in payload["cases"]] == [
        "stage1-extracts-temporal-and-object-facts",
        "stage2-detects-reversed-temporal-order",
        "e2e-detects-temporal-contradiction-without-cloak-false-positive",
    ]


def test_drift_parser_reads_pydantic_eval_report(tmp_path: Path) -> None:
    report_path = tmp_path / "suite.json"
    report_path.write_text(
        json.dumps(
            {
                "framework": "pydantic-evals",
                "cases": [
                    {"name": "case-a", "scores": {"Quality": 0.75}, "assertions": {}},
                    {"name": "case-b", "scores": {}, "assertions": {"Valid": True}},
                ],
            }
        ),
        encoding="utf-8",
    )

    parsed = parse_pydantic_eval_report(report_path)

    assert parsed.source == "suite"
    assert [case.name for case in parsed.test_cases] == ["case-a", "case-b"]
    assert parsed.test_cases[0].avg_score == 0.75
    assert parsed.test_cases[1].avg_score == 1.0


# ---------------------------------------------------------------------------
# Regression: run_suites() must not leak an open asyncio event loop
# ---------------------------------------------------------------------------
#
# Bug history: ``pydantic_evals.Dataset.evaluate_sync()`` delegates to
# ``pydantic_evals._utils.get_event_loop()`` which calls
# ``asyncio.new_event_loop()`` + ``asyncio.set_event_loop()`` when invoked
# from a sync context with no running loop — but **never closes the loop**.
# The leaked loop holds a unix-socket self-pair (fd pair from
# ``BaseSelectorEventLoop._make_self_pipe``) that is released only when the
# loop object is garbage-collected.
#
# Symptom: when the evals tests ran together with tests that call
# ``asyncio.run()`` (which resets the policy's current loop to ``None``),
# the pydantic-evals loop became unreachable. At session teardown,
# ``pytest_unconfigure`` calls ``gc.collect()``, finalizing the loop and
# emitting ``ResourceWarning: unclosed <socket.socket fd=NN, family=1,
# type=1, proto=0>``. pytest's unraisable-exception plugin turns this into
# ``PytestUnraisableExceptionWarning`` → ``ExceptionGroup`` → exit code 1
# even though all tests passed.
#
# The existing ``ignore:.*qdrant.*`` ``filterwarnings`` rule did NOT catch
# these warnings (the message contains no "qdrant" substring).
#
# Root cause: third-party bug in pydantic-evals' ``get_event_loop()``.
# Fix: ``evals/runner.py`` closes the leaked loop after every
# ``evaluate_sync()`` call (see ``_close_pydantic_evals_leaked_event_loop``).
#
# This test verifies the fix by forcing collection of the loop and asserting
# no ``ResourceWarning`` fires.


def test_run_suites_does_not_leak_open_event_loop(tmp_path: Path) -> None:
    """Regression: run_suites() must close the event loop it (indirectly) creates.

    pydantic-evals' ``evaluate_sync()`` → ``get_event_loop()`` creates a new
    asyncio event loop when called from sync code but never closes it.
    The loop holds a unix-socket self-pair that triggers
    ``ResourceWarning`` at GC time, surfacing as
    ``PytestUnraisableExceptionWarning`` at session teardown.

    This test forces GC of the loop after dropping the policy reference.
    If the loop is still open, its ``__del__`` emits ``ResourceWarning``
    about the unclosed sockets, which we promote to an error.
    """
    # Allow asyncio's own DeprecationWarnings (set_event_loop goes through
    # the policy) but promote ResourceWarning — the actual leak signal — to
    # an error.
    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=ResourceWarning)
        warnings.filterwarnings("default", category=DeprecationWarning)

        # Ensure clean starting state so pydantic-evals creates a fresh loop
        # rather than reusing a pre-existing one.
        asyncio.set_event_loop(None)

        run_suites(
            suite="rewrite_selection",
            mode="smoke",
            results_dir=tmp_path,
            minimum_score=0.8,
            judge_model=None,
        )

        # Drop the policy's reference so the loop becomes collectible.
        # (``run_suites`` should have already closed it — if not, this makes
        # the still-open loop eligible for GC, which will fire ResourceWarning.)
        asyncio.set_event_loop(None)

        # If the loop was left open, gc.collect() finalizes it now and its
        # ``__del__`` emits ``ResourceWarning: unclosed <socket.socket ...>``.
        gc.collect()


# ---------------------------------------------------------------------------
# Graceful runtime skip for smoke-only suites (AUFG-03-07 increment #5d)
# ---------------------------------------------------------------------------
#
# Background: per the eval-expansion plan, three suites (analysis_metrics,
# kb_operations, planning_structure) are smoke-only — they have no runtime
# task because their agents are not Tier-1. Previously,
# ``RuntimeTaskFactory.build()`` raised ``ValueError`` for these suites,
# which crashed ``--suite all --mode runtime`` (the nightly workflow) on
# the first smoke-only suite.
#
# The fix (increment #5d) introduces ``available_suites()`` on both
# factories and an ``available_suites_for_mode(mode)`` helper. The runner
# filters requested suites against the runtime registry up front and prints
# a clear skip notice per smoke-only suite rather than crashing. Real
# runtime failures (provider errors, score regressions) still surface.


# Suites that are intentionally smoke-only (no runtime task).
SMOKE_ONLY_SUITES = {"analysis_metrics", "kb_operations", "planning_structure"}

# All registered datasets — derived single-source from the registry so
# adding a suite never silently desyncs this set from ``evals.datasets``.
ALL_SUITES = set(available_suites())


def test_smoke_factory_available_suites_includes_all_registered_datasets() -> None:
    """Smoke factory has a task for every registered dataset."""

    available = set(SmokeTaskFactory().available_suites())
    assert available == ALL_SUITES


def test_runtime_factory_available_suites_excludes_smoke_only() -> None:
    """Runtime factory exposes Tier-1 suites only, not the smoke-only three.

    This is the single-source predicate the runner uses to skip — it must
    not be hardcoded elsewhere.
    """

    available = set(RuntimeTaskFactory.from_env().available_suites())
    assert available == ALL_SUITES - SMOKE_ONLY_SUITES
    assert SMOKE_ONLY_SUITES.isdisjoint(available)


def test_available_suites_for_mode_smoke_includes_all() -> None:
    assert set(available_suites_for_mode("smoke")) == ALL_SUITES


def test_available_suites_for_mode_runtime_excludes_smoke_only() -> None:
    assert set(available_suites_for_mode("runtime")) == ALL_SUITES - SMOKE_ONLY_SUITES


def test_available_suites_for_mode_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported eval mode"):
        available_suites_for_mode("bogus")


def test_get_task_smoke_only_suite_in_runtime_mode_still_raises() -> None:
    """Direct ``get_task()`` for a smoke-only suite is a programmer error.

    The runner is responsible for filtering; calling ``get_task`` directly
    with a non-runtime suite must surface as ``ValueError`` so silent
    misconfiguration can't slip through.
    """

    with pytest.raises(ValueError, match="Unknown eval suite: analysis_metrics"):
        get_task("analysis_metrics", "runtime")


def test_run_suites_runtime_skips_smoke_only_suite_gracefully(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Asking for a smoke-only suite in runtime mode exits 0 with a notice.

    No runtime task is invoked (and thus no provider API key is needed).
    The skip is logged to stdout for nightly CI visibility.
    """

    exit_code = _run_suites_safe(
        suite="analysis_metrics",
        mode="runtime",
        results_dir=tmp_path,
        minimum_score=0.8,
        judge_model=None,
    )

    assert exit_code == 0
    # No report should be written for a skipped suite.
    assert not (tmp_path / "analysis_metrics.json").exists()

    captured = capsys.readouterr()
    assert "analysis_metrics" in captured.out
    assert "smoke-only" in captured.out
    assert "skipping" in captured.out


def test_run_suites_runtime_all_skips_smoke_only_and_reports_each(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--suite all --mode runtime`` must not crash on smoke-only suites.

    We can't exercise the real runtime tasks here (no provider secret), so
    this test monkey-patches ``get_task`` to a stub that records which
    suites the runner actually tried to invoke. The three smoke-only
    suites must NOT appear in that record.
    """

    import evals.runner as runner_mod

    invoked: list[str] = []

    async def _stub_task(_inputs: object) -> object:
        return {}

    original_get_task = runner_mod.get_task

    def _recording_get_task(suite: str, mode: str) -> object:
        invoked.append(suite)
        return _stub_task

    # ``get_task`` is imported into the runner module namespace, so patch
    # it there (not in evals.tasks).
    runner_mod.get_task = _recording_get_task  # type: ignore[assignment]
    try:
        exit_code = _run_suites_safe(
            suite="all",
            mode="runtime",
            results_dir=tmp_path,
            minimum_score=0.0,
            judge_model=None,
        )
    finally:
        runner_mod.get_task = original_get_task  # type: ignore[assignment]

    # Exit code is non-zero only because the stub returns an empty dict
    # which fails eval assertions — that's fine; we're verifying the
    # *filtering*, not the stub's output. The key assertions are below.
    assert exit_code in (0, 1)

    captured = capsys.readouterr()
    # Each smoke-only suite is mentioned by name in a skip notice.
    for name in SMOKE_ONLY_SUITES:
        assert name in captured.out, f"expected skip notice for {name}"
        assert "smoke-only" in captured.out

    # And critically: the runner never tried to invoke a task for them.
    for name in SMOKE_ONLY_SUITES:
        assert name not in invoked, (
            f"runner should not have invoked get_task for smoke-only suite {name}"
        )
    # Runtime-capable suites WERE invoked (proving we didn't over-skip).
    expected_runtime = ALL_SUITES - SMOKE_ONLY_SUITES
    assert set(invoked) == expected_runtime
