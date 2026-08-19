"""CLI logic, argument parsing, and the importable ``check_type_ignores`` function."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .baseline import (
    DEFAULT_BASELINE_PATH,
    BaselineShrinkError,
    ComparisonResult,
    compare_against_baseline,
    load_baseline,
    save_baseline,
)
from .reporter import build_json_output, print_report
from .scanner import ScanResult, scan_codebase
from .staged import run_staged_mode


def _determine_exit_code(result: ScanResult, comparison: ComparisonResult | None) -> int:
    """Exit code from scan result + baseline comparison (single source).

    ERROR (2): naked ignores, production suppressions without reason,
    production total above baseline (production delta must stay ≤ 0).
    WARNING (1): suppression budget growth — total or test budget above
    the frozen baseline (ratchet-down; blocking in CI because any
    non-zero exit fails the step).
    """
    exit_code = 0

    # ERROR conditions
    if result.naked_ignores:
        exit_code = 2
    if comparison and comparison.production_delta > 0:
        exit_code = max(exit_code, 2)
    if result.uncommented_ignores:
        exit_code = max(exit_code, 2)

    # WARNING conditions (only if no ERROR already)
    if exit_code == 0 and comparison and (comparison.total_delta > 0 or comparison.test_delta > 0):
        exit_code = 1

    return exit_code


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

    exit_code = _determine_exit_code(result, comparison)

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
            "  1  Budget growth: total or test suppression count exceeds the\n"
            "     frozen baseline (ratchet-down; blocking in CI)\n"
            "  2  Errors (naked ignores / production baseline exceeded / "
            "uncommented suppressions)\n\n"
            "Examples:\n"
            "  python -m scripts.check_type_ignores\n"
            "  python -m scripts.check_type_ignores --staged\n"
            "  python -m scripts.check_type_ignores --baseline my-baseline.json\n"
            "  python -m scripts.check_type_ignores --update-baseline \\\n"
            "      --allow-removed path/to/cleaned_file.py\n"
        ),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="Path to baseline JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--update-baseline",
        dest="update_baseline",
        action="store_true",
        help=(
            "Capture the current scan state as the new baseline (guarded: "
            "files-keys that disappear must be named via --allow-removed)"
        ),
    )
    parser.add_argument(
        "--allow-removed",
        dest="allow_removed",
        default="",
        metavar="FILES",
        help=(
            "With --update-baseline: comma-separated baseline file keys that "
            "deliberately disappear in this run (suppressions fully removed "
            "or file deleted). Must name the disappearing keys exactly, "
            "one-for-one — a mismatch (missing or overstated) aborts the "
            "update."
        ),
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help=(
            "Fast pre-commit scope: scan only .py files staged in the git "
            "index and check them against the per-file baseline counts"
        ),
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

    baseline_path: Path = args.baseline

    # ── Staged-files mode (pre-commit hook; no full scan needed) ──
    if args.staged:
        return run_staged_mode(baseline_path)

    # ── Scan ──
    result = scan_codebase()

    # ── Baseline update (guarded; removals must be named) ──
    if args.update_baseline:
        allow_removed = {k.strip() for k in args.allow_removed.split(",") if k.strip()}
        try:
            wrote = save_baseline(result, baseline_path, allow_removed=allow_removed)
        except BaselineShrinkError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        if not wrote:
            print(f"Note: baseline already current, left untouched: {baseline_path}")
            return 0
        if allow_removed:
            # After a successful save, allow_removed is guaranteed (by the
            # guard) to equal the actually-removed keys — the audit line.
            print(
                f"Removed {len(allow_removed)} baseline key(s): " + ", ".join(sorted(allow_removed))
            )
        print(
            f"✅  Baseline updated: {baseline_path}  "
            f"({result.total} suppressions: {result.production_total} "
            f"production / {result.test_total} test)"
        )
        return 0

    # ── Compare ──
    baseline_data = load_baseline(baseline_path)
    comparison = compare_against_baseline(result, baseline_data) if baseline_data else None

    # ── Determine exit code ──
    exit_code = _determine_exit_code(result, comparison)

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
            grown: list[str] = []
            if comparison:
                if comparison.total_delta > 0:
                    grown.append(f"total {comparison.total_delta:+d}")
                if comparison.test_delta > 0:
                    grown.append(f"test budget {comparison.test_delta:+d}")
            print(
                "⚠️   RULE-23: WARNING — suppression budget exceeds baseline ("
                + ", ".join(grown)
                + "); the ratchet only allows reductions. Deliberate changes "
                "require --update-baseline (disappearing keys: --allow-removed)."
            )
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
