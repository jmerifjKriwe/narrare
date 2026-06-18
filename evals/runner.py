"""CLI runner for Narrare Pydantic Evals suites."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from evals.datasets import DATASET_FACTORIES, available_suites
from evals.judges import add_optional_llm_judge
from evals.reports import write_report_json
from evals.tasks import get_task

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
    """Run one or more eval suites and write JSON reports."""

    suites = available_suites() if suite == "all" else [suite]
    failed = False
    for suite_name in suites:
        dataset = DATASET_FACTORIES[suite_name]()
        add_optional_llm_judge(dataset, suite_name, judge_model)
        task = get_task(suite_name, mode)
        report = dataset.evaluate_sync(task)
        # pydantic-evals' ``evaluate_sync`` → ``_utils.get_event_loop()``
        # creates a new asyncio event loop when invoked from sync code but
        # never closes it. The leaked loop holds a unix-socket self-pair
        # that triggers ``ResourceWarning`` at GC time — surfacing as
        # ``PytestUnraisableExceptionWarning`` at pytest session teardown
        # and as stderr noise at interpreter shutdown. Close it
        # deterministically so ``run_suites`` is safe to call from
        # long-running processes and from tests.
        _close_pydantic_evals_leaked_event_loop()
        report.print(include_input=True, include_output=True, include_durations=False)
        write_report_json(report, results_dir / f"{suite_name}.json", suite=suite_name, mode=mode)
        failed = _has_failures(report) or _average_score(report) < minimum_score or failed
    return 1 if failed else 0


def _close_pydantic_evals_leaked_event_loop() -> None:
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

    Implementation note: accessing the policy's thread-local "current
    event loop" in Python 3.14 requires ``asyncio.get_event_loop_policy``
    which is deprecated (slated for removal in 3.16). There is no
    non-deprecated alternative for this specific use case (the modern
    ``asyncio.Runner`` API does not apply — we did not create the loop).
    The DeprecationWarning is suppressed locally with a narrow filter so
    it does not leak into callers or trip the project's
    ``filterwarnings = ["error", ...]`` pytest configuration.
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
            loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            # No current event loop set — nothing to close.
            asyncio.set_event_loop(None)
            return
    if loop.is_running():
        # Don't close a loop that's actively running — that would break
        # the caller. (Shouldn't happen for ``evaluate_sync`` from sync
        # code, but guard anyway.)
        return
    if not loop.is_closed():
        loop.close()
    asyncio.set_event_loop(None)


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
