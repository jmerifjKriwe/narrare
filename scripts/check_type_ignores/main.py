"""CLI logic, argument parsing, and the importable ``check_type_ignores`` function."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .baseline import (
    DEFAULT_BASELINE_PATH,
    ComparisonResult,
    build_baseline_dict,
    compare_against_baseline,
    load_baseline,
)
from .reporter import build_json_output, print_report
from .scanner import scan_codebase


def check_type_ignores(baseline_path: str | None = None) -> dict[str, Any]:
    """Run the full type-ignore discipline check and return results.

    Parameters
    ----------
    baseline_path:
        Optional path to a baseline JSON file.  When ``None`` the default
        baseline is used; when the baseline file does not exist the comparison
        is skipped.

    Returns
    -------
    A dictionary with these keys:

    * ``scan`` — :class:`ScanResult` (dataclass, converted to dict)
    * ``comparison`` — :class:`ComparisonResult` or ``None``
    * ``exit_code`` — 0 (pass), 1 (warning), 2 (error)
    * ``json`` — machine-readable JSON dict for CI
    """
    result = scan_codebase()

    baseline: dict[str, Any] = {}
    if baseline_path is not None:
        baseline = load_baseline(Path(baseline_path))
    else:
        baseline = load_baseline(DEFAULT_BASELINE_PATH)

    comparison: ComparisonResult | None = (
        compare_against_baseline(result, baseline) if baseline else None
    )

    # Determine exit code
    exit_code = 0

    # ERROR conditions
    if result.naked_ignores:
        exit_code = 2
    if comparison and comparison.production_delta > 0:
        exit_code = max(exit_code, 2)
    if result.uncommented_ignores:
        exit_code = max(exit_code, 2)

    # WARNING conditions (only if no ERROR already)
    if exit_code == 0 and comparison and comparison.total_delta > 0:
        exit_code = 1

    json_output = build_json_output(result, comparison)

    return {
        "scan": result,
        "comparison": comparison,
        "exit_code": exit_code,
        "json": json_output,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Narrare Type-Ignore Discipline Checker (RULE-23)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  All checks pass\n"
            "  1  Warnings (total suppression count exceeds baseline)\n"
            "  2  Errors (naked ignores / production baseline exceeded / "
            "uncommented suppressions)\n\n"
            "Examples:\n"
            "  python -m scripts.check_type_ignores\n"
            "  python -m scripts.check_type_ignores --update\n"
            "  python -m scripts.check_type_ignores --baseline my-baseline.json\n"
        ),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="Path to baseline JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update (create / overwrite) the baseline file from current scan state",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON to stdout (in addition to human report on stderr)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code."""
    args = _parse_args(argv)

    # ── Scan ──
    result = scan_codebase()

    # ── Baseline ──
    baseline_path: Path = args.baseline
    if args.update:
        baseline_dict = build_baseline_dict(result)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with baseline_path.open("w", encoding="utf-8") as fh:
            json.dump(baseline_dict, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"✅  Baseline updated: {baseline_path}  ({result.total} suppressions)")
        return 0

    # ── Compare ──
    baseline_data = load_baseline(baseline_path)
    comparison = compare_against_baseline(result, baseline_data) if baseline_data else None

    # ── Determine exit code ──
    exit_code = 0

    if result.naked_ignores:
        exit_code = 2
    if comparison and comparison.production_delta > 0:
        exit_code = max(exit_code, 2)
    if result.uncommented_ignores:
        exit_code = max(exit_code, 2)

    if exit_code == 0 and comparison and comparison.total_delta > 0:
        exit_code = 1

    # ── Human-readable report ──
    # If --json is set, send the human report to stderr so stdout stays clean
    output_stream = sys.stderr if args.json else sys.stdout
    _orig_stdout = sys.stdout
    sys.stdout = output_stream
    try:
        print_report(result, comparison)

        if exit_code == 0:
            print("✅  RULE-23: All type-ignore discipline checks pass")
        elif exit_code == 1:
            print("⚠️   RULE-23: WARNING — total suppression count exceeds baseline")
        else:
            print("❌  RULE-23: FAILED — type-ignore discipline violations detected")
        print()
    finally:
        sys.stdout = _orig_stdout

    # ── Machine-readable JSON ──
    if args.json:
        json_output = build_json_output(result, comparison)
        json_output["exit_code"] = exit_code
        print(json.dumps(json_output, indent=2, ensure_ascii=False))

    return exit_code
