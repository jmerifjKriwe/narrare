"""CLI runner for Narrare Pydantic Evals suites."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from evals.datasets import DATASET_FACTORIES, available_suites
from evals.judges import add_optional_llm_judge
from evals.reports import write_report_json
from evals.tasks import available_suites_for_mode, get_task

DEFAULT_RESULTS_DIR = Path("evals/results")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Run Narrare Pydantic Evals")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Run eval suites")
    run_parser.add_argument("--suite", choices=["all", *available_suites()], default="all")
    run_parser.add_argument("--mode", choices=["smoke", "runtime"], default="smoke")
    run_parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    run_parser.add_argument("--fail-on-score-below", type=float, default=0.8)
    run_parser.add_argument(
        "--judge-model",
        default=None,
        help="Optional LLMJudge model string, e.g. openai:gpt-5-mini. Disabled by default.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the eval CLI."""

    args = parse_args(argv)
    if args.command == "run":
        return run_suites(
            suite=args.suite,
            mode=args.mode,
            results_dir=args.results_dir,
            minimum_score=args.fail_on_score_below,
            judge_model=args.judge_model,
        )
    raise ValueError(f"Unsupported command: {args.command}")


def run_suites(
    suite: str,
    mode: str,
    results_dir: Path,
    minimum_score: float,
    judge_model: str | None = None,
) -> int:
    """Run one or more eval suites and write JSON reports.

    For ``mode="runtime"`` suites without a runtime task (Tier 2/3
    smoke-only suites per the eval-expansion plan) are reported and
    skipped rather than crashing. Real runtime failures (provider
    errors, score regressions) still produce a non-zero exit code.
    """

    requested = available_suites() if suite == "all" else [suite]
    suites = _resolve_runnable_suites(requested, mode)
    if not suites:
        return 0

    failed = False

    # Save the current event loop (may be pytest-asyncio session loop).
    # pydantic-evals' evaluate_sync may create or reuse an event loop;
    # we must not close the session loop if evaluate_sync reused it.
    saved_loop = _get_current_loop_safe()

    for suite_name in suites:
        dataset = DATASET_FACTORIES[suite_name]()
        add_optional_llm_judge(dataset, suite_name, judge_model)
        task = get_task(suite_name, mode)
        report = dataset.evaluate_sync(task)
        # Close any loop that pydantic-evals created — but NOT the saved
        # session loop (pytest-asyncio's session-scoped event loop).
        _close_pydantic_evals_leaked_event_loop(saved_loop=saved_loop)
        report.print(include_input=True, include_output=True, include_durations=False)
        write_report_json(report, results_dir / f"{suite_name}.json", suite=suite_name, mode=mode)
        failed = _has_failures(report) or _average_score(report) < minimum_score or failed

    # Restore the saved event loop if it's still valid.
    _restore_loop_safe(saved_loop)

    return 1 if failed else 0


def _resolve_runnable_suites(requested: list[str], mode: str) -> list[str]:
    """Filter *requested* suites against the task registry for *mode*.

    For ``mode="runtime"`` the registry intentionally omits Tier 2/3
    smoke-only suites. We print a clear notice per skipped suite and
    return only the suites that actually have a task. For
    ``mode="smoke"`` every dataset has a task so no filtering occurs.
    """

    if mode == "smoke":
        return requested

    capable = set(available_suites_for_mode(mode))
    runnable: list[str] = []
    for name in requested:
        if name in capable:
            runnable.append(name)
        else:
            print(f"[runtime] no runtime task for suite '{name}' (smoke-only) — skipping")
    if not runnable:
        print(f"[runtime] no runtime-capable suites among {requested!r}; nothing to run (exit 0).")
    return runnable


def _get_current_loop_safe():
    """Get the current event loop from the policy, or None if not set.

    Suppresses DeprecationWarning for ``get_event_loop_policy`` (slated
    for removal in Python 3.16).
    """
    import asyncio
    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*get_event_loop_policy.*",
            category=DeprecationWarning,
        )
        try:
            return asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            return None


def _close_pydantic_evals_leaked_event_loop(
    saved_loop: asyncio.AbstractEventLoop | None = None,
) -> None:
    """Close the event loop leaked by ``pydantic_evals.Dataset.evaluate_sync``.

    pydantic-evals' ``_utils.get_event_loop()`` calls
    ``asyncio.new_event_loop()`` + ``asyncio.set_event_loop()`` when there
    is no running loop, but never closes the loop. The loop owns a
    unix-socket self-pair (see
    ``asyncio.selector_events.BaseSelectorEventLoop._make_self_pipe``)
    that is released only when the loop is explicitly closed or when the
    loop object is garbage-collected — at which point its ``__del__``
    emits ``ResourceWarning``.

    Upstream bug: ``pydantic-evals`` does not close loops it creates via
    ``get_event_loop()``. This helper is the local workaround: it closes
    the policy's current event loop if one exists and is not running,
    then clears the reference so it does not linger until interpreter
    shutdown.

    Safe to call when there is no leaked loop (no-op) and when called
    from within a running loop (no-op — the running loop is left alone).

    Args:
        saved_loop: The event loop that was current BEFORE evaluate_sync
            was called, or None. If provided and matching the current
            loop, the loop is left alone (pydantic-evals reused the
            existing loop rather than creating a new one). If None,
            any available loop is closed (backward-compatible behavior).

    Implementation note: accessing the policy's thread-local "current
    event loop" in Python 3.14 requires ``asyncio.get_event_loop_policy``
    which is deprecated (slated for removal in 3.16). There is no
    non-deprecated alternative for this specific use case (the modern
    ``asyncio.Runner`` API does not apply — we did not create the loop).
    The DeprecationWarning is suppressed locally with a narrow filter so
    it does not leak into callers or trip the project's
    ``filterwarnings = ["error", ...]`` pytest configuration.
    """

    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*get_event_loop_policy.*",
            category=DeprecationWarning,
        )
        try:
            current_loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            # No current event loop — nothing to close.
            return
    if current_loop.is_running():
        # Don't close a loop that's actively running — that would break
        # the caller. (Shouldn't happen for ``evaluate_sync`` from sync
        # code, but guard anyway.)
        return

    # If saved_loop is provided and matches current_loop, pydantic-evals
    # reused the existing loop — don't close it! Only close if
    # pydantic-evals created a NEW loop.
    if saved_loop is not None and current_loop is saved_loop:
        return

    if not current_loop.is_closed():
        current_loop.close()
    asyncio.set_event_loop(None)


def _restore_loop_safe(saved_loop: asyncio.AbstractEventLoop | None) -> None:
    """Restore a previously saved event loop if it's still valid.

    Args:
        saved_loop: The event loop to restore, or None. If None, cleans
            up any leaked loop and ensures clean state.
    """
    import warnings

    if saved_loop is None:
        # No saved loop — ensure clean state by clearing any leaked loop.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r".*get_event_loop_policy.*",
                category=DeprecationWarning,
            )
            try:
                current = asyncio.get_event_loop_policy().get_event_loop()
            except RuntimeError:
                current = None
            if current is not None and not current.is_running() and not current.is_closed():
                current.close()
        asyncio.set_event_loop(None)
        return

    if not saved_loop.is_closed():
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r".*get_event_loop_policy.*",
                category=DeprecationWarning,
            )
            asyncio.set_event_loop(saved_loop)


def _has_failures(report: object) -> bool:
    return bool(getattr(report, "failures", []))


def _average_score(report: object) -> float:
    values: list[float] = []
    for case in getattr(report, "cases", []):
        scores: Any = getattr(case, "scores", {})
        for result in scores.values():
            value = getattr(result, "value", None)
            if isinstance(value, (int, float)):
                values.append(float(value))
    if not values:
        return 1.0
    return sum(values) / len(values)
