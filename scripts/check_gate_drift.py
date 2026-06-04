#!/usr/bin/env python3
"""
Narrare Gate Drift Checker.

Detects drift between documented quality gates and CI configuration.
Compares gate-exceptions.json, CI YAML, pyproject.toml, and quality-gates
documentation to find mismatches.

Exit codes:
  0: All drift has registered exceptions (or no drift found).
  1: Unregistered drift detected — CI does not match docs.

Usage:
  python scripts/check_gate_drift.py                   # human-readable
  python scripts/check_gate_drift.py --json            # JSON for CI

See: .opencode/context/narrare-dev/processes/quality-gates.md Gate 11.
"""

from __future__ import annotations

import argparse
import json
import sys

from gate_drift_checks import DriftReport, run_all_checks

# ── Report generation ──────────────────────────────────────────


def print_human_report(report: DriftReport) -> None:
    """Print a human-readable drift report."""
    print("GATE DRIFT REPORT")
    print("=" * 70)

    for item in report.items:
        if item.passed:
            print(f"✅ {item.check_id}: {item.detail}")
        elif item.has_exception:
            print(f"⚠️  {item.check_id}: {item.detail}")
        else:
            print(f"❌ {item.check_id}: {item.detail}")

    print()
    if report.has_unregistered_drift:
        print(
            f"Summary: {report.criticals} critical, {report.warnings} warnings "
            f"(unregistered drift found!)"
        )
    else:
        print(
            f"Summary: {report.criticals} critical, {report.warnings} warnings "
            f"(all drifts have registered exceptions)"
        )


def print_json_report(report: DriftReport) -> None:
    """Print a JSON-formatted report for CI pipeline consumption."""
    output = {
        "exit_code": 1 if report.has_unregistered_drift else 0,
        "has_unregistered_drift": report.has_unregistered_drift,
        "criticals": report.criticals,
        "warnings": report.warnings,
        "items": [
            {
                "check_id": item.check_id,
                "passed": item.passed,
                "detail": item.detail,
                "has_exception": item.has_exception,
                "exception_id": item.exception_id,
                "is_ok": item.is_ok,
            }
            for item in report.items
        ],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


# ── CLI entry point ────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Narrare Gate Drift Checker — docs vs CI reality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  No unregistered drift (all drifts have exceptions)\n"
            "  1  Unregistered drift detected\n"
            "\n"
            "Examples:\n"
            "  python scripts/check_gate_drift.py\n"
            "  python scripts/check_gate_drift.py --json\n"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (for CI consumption)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run all drift checks and return the exit code."""
    args = parse_args(argv)
    report = run_all_checks()

    if args.json:
        print_json_report(report)
    else:
        print_human_report(report)

    return 1 if report.has_unregistered_drift else 0


if __name__ == "__main__":
    sys.exit(main())
