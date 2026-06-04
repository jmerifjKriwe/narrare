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
    DEFAULT_RESULTS_DIR,
    DEFAULT_THRESHOLD,
    EvalResultFile,
    find_result_files,
    parse_promptfoo_results,
)
from .reporting import print_human_report, print_json_report


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
        help=(f"Directory containing promptfoo eval JSON results (default: {DEFAULT_RESULTS_DIR})"),
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the eval drift checker.

    Returns:
        0: No significant drift (or no baselines to compare against).
        1: Drift detected -- score drop exceeds threshold.
    """
    args = parse_args(argv)

    results_dir: Path = args.results_dir
    baselines_dir: Path = args.baselines_dir
    threshold: float = args.threshold

    # -- Discover result files --
    result_files = find_result_files(results_dir)

    if not result_files:
        if args.json_output:
            print(
                json.dumps(
                    {
                        "has_drift": False,
                        "drift_count": 0,
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
            print("Run promptfoo eval to generate results first.")
        return 0

    # -- Parse all results --
    eval_results: list[EvalResultFile] = []
    for filepath in result_files:
        result = parse_promptfoo_results(filepath)
        if result.test_cases:
            eval_results.append(result)

    if not eval_results:
        if args.json_output:
            print(
                json.dumps(
                    {
                        "has_drift": False,
                        "drift_count": 0,
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
    report = compare_against_baselines(eval_results, baselines_dir, threshold)

    if args.json_output:
        print_json_report(report, threshold)
    else:
        print_human_report(report, threshold)

    # -- Exit code --
    if report.has_drift:
        return 1

    return 0
