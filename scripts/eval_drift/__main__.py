"""CLI entry point for eval drift checking.

Provides argument parsing and the main orchestration function that
ties together parsing, comparison, and reporting.

See: docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .comparison import compare_against_baselines, update_baselines
from .parser import (
    DEFAULT_BASELINES_DIR,
    DEFAULT_PRIORITIES_FILE,
    DEFAULT_RESULTS_DIR,
    DEFAULT_THRESHOLD,
    EvalResultFile,
    find_result_files,
    parse_pydantic_eval_report,
)
from .priorities import Priorities
from .reporting import print_human_report, print_json_report

# The only priority level that gates CI today. Restricting via ``choices``
# makes an unsupported level a hard CLI error rather than a silent no-op.
_P0_LEVEL = "P0"
_OFF_MODE = "off"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Narrare Eval Baseline Drift Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/check_eval_drift.py\n"
            "  python scripts/check_eval_drift.py --json\n"
            "  python scripts/check_eval_drift.py --threshold 0.10\n"
            "  python scripts/check_eval_drift.py --update-baselines\n"
        ),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help=(f"Directory containing Pydantic Evals JSON results (default: {DEFAULT_RESULTS_DIR})"),
    )
    parser.add_argument(
        "--baselines-dir",
        type=Path,
        default=DEFAULT_BASELINES_DIR,
        help=(f"Directory containing baseline JSON files (default: {DEFAULT_BASELINES_DIR})"),
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=(
            f"Maximum allowed score drop before failing (default: {DEFAULT_THRESHOLD}, i.e. 5%%)"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON (for CI consumption)",
    )
    parser.add_argument(
        "--update-baselines",
        action="store_true",
        help="Copy current results as new baselines instead of checking drift",
    )
    parser.add_argument(
        "--priorities",
        type=Path,
        default=DEFAULT_PRIORITIES_FILE,
        help=(
            "P0 priority manifest (suite -> [cases]). Decoupled from baselines "
            f"so --update-baselines never overwrites it (default: {DEFAULT_PRIORITIES_FILE})"
        ),
    )
    parser.add_argument(
        "--fail-on-priority",
        choices=[_P0_LEVEL],
        default=None,
        help=(
            "Gate the exit code on P0 regressions only: exit 1 iff a P0 case "
            "drifts; non-P0 drift stays a non-blocking WARNING. Omit to keep "
            "legacy behaviour (any drift exits 1)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the eval drift checker.

    Returns:
        0: No blocking drift (see exit-mode note below).
        1: Blocking drift detected -- a score drop exceeds threshold on a
           case the active exit mode gates on.
    """
    args = parse_args(argv)

    results_dir: Path = args.results_dir
    baselines_dir: Path = args.baselines_dir
    threshold: float = args.threshold

    # P0 priority manifest (decoupled from baselines). Loaded unconditionally so
    # every comparison carries an is_p0 label for reporting, even when the exit
    # code is not gated on it. A missing manifest yields an empty Priorities.
    priorities = Priorities.from_manifest(args.priorities)
    priority_mode: str = _P0_LEVEL if args.fail_on_priority == _P0_LEVEL else _OFF_MODE

    # -- Discover result files --
    result_files = find_result_files(results_dir)

    if not result_files:
        if args.json_output:
            print(
                json.dumps(
                    {
                        "has_drift": False,
                        "drift_count": 0,
                        "p0_drift_count": 0,
                        "priority_mode": priority_mode,
                        "threshold": threshold,
                        "comparisons": [],
                        "missing_baselines": [],
                        "errors": [f"No result files found in {results_dir}"],
                    },
                    indent=2,
                )
            )
        else:
            print(f"No eval result files found in {results_dir}")
            print("Run `python -m evals run --suite all --mode smoke` to generate results first.")
        return 0

    # -- Parse all results --
    eval_results: list[EvalResultFile] = []
    for filepath in result_files:
        result = parse_pydantic_eval_report(filepath)
        if result.test_cases:
            eval_results.append(result)

    if not eval_results:
        if args.json_output:
            print(
                json.dumps(
                    {
                        "has_drift": False,
                        "drift_count": 0,
                        "p0_drift_count": 0,
                        "priority_mode": priority_mode,
                        "threshold": threshold,
                        "comparisons": [],
                        "missing_baselines": [],
                        "errors": ["Result files exist but contain no parseable test cases"],
                    },
                    indent=2,
                )
            )
        else:
            print("Found result files but could not parse any test cases.")
            print("The files may be empty or in an unexpected format.")
        return 0

    # -- Update baselines mode --
    if args.update_baselines:
        updated = update_baselines(eval_results, baselines_dir)
        if args.json_output:
            print(
                json.dumps(
                    {"updated": updated, "count": len(updated)},
                    indent=2,
                )
            )
        else:
            print(f"Updated {len(updated)} baseline file(s):")
            for name in updated:
                print(f"   \u2022 {name}")
        return 0

    # -- Compare against baselines --
    report = compare_against_baselines(eval_results, baselines_dir, threshold, priorities)

    if args.json_output:
        print_json_report(report, threshold, priority_mode)
    else:
        print_human_report(report, threshold, priority_mode)

    # -- Exit code --
    # In P0 mode the exit code gates ONLY on P0 regressions; non-P0 drift is
    # surfaced as a WARNING in the report but never fails the run. Without
    # --fail-on-priority the legacy behaviour is preserved (any drift -> 1).
    if priority_mode == _P0_LEVEL:
        return 1 if report.has_p0_drift else 0

    return 1 if report.has_drift else 0
