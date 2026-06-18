"""Unit tests for Pydantic Evals runner serialization and drift parsing."""

from __future__ import annotations

import asyncio
import gc
import json
import warnings
from typing import TYPE_CHECKING

from evals.runner import run_suites
from scripts.eval_drift.parser import parse_pydantic_eval_report

if TYPE_CHECKING:
    from pathlib import Path


def test_runner_writes_smoke_report(tmp_path: Path) -> None:
    exit_code = run_suites(
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
    exit_code = run_suites(
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
