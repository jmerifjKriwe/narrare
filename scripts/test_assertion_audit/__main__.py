"""CLI entry point for test assertion audit.

Provides argument parsing and orchestrates scanning, filtering, and
reporting of weak test assertion patterns.

Usage:
    uv run python scripts/audit_test_assertions.py
    uv run python scripts/audit_test_assertions.py --path tests/unit/ --top-n 10
    uv run python scripts/audit_test_assertions.py --json report.json --fail-on 0.5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import FileReport

from .report import format_json, format_report
from .scanner import scan_directory, scan_file


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Scan Python test files for weak assertion patterns (AST-based).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        action="append",
        default=None,
        help=(
            "Test directories to scan (can be repeated). "
            "Defaults to tests/unit and tests/integration."
        ),
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="Score threshold for warning display (default: 0.3)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        dest="top_n",
        help="Only show top N files by score (default: 30)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        dest="json_path",
        help="Write JSON report to this file path",
    )
    parser.add_argument(
        "--fail-on",
        type=float,
        default=None,
        dest="fail_on",
        help="Exit with code 1 if any file's score exceeds this threshold",
    )
    return parser


def _resolve_test_dirs(given_dirs: list[Path] | None) -> list[Path]:
    """Resolve the list of directories to scan.

    Falls back to ``tests/unit`` and ``tests/integration`` relative to repo
    root if nothing is given.
    """
    if given_dirs is not None and len(given_dirs) > 0:
        return [d.resolve() for d in given_dirs]

    # Auto-detect repo root (three parents up: __main__ → package → scripts → repo).
    repo_root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        repo_root / "tests" / "unit",
        repo_root / "tests" / "integration",
    ]
    return [c for c in candidates if c.exists()]


def _collect_reports(paths: list[Path], threshold: float) -> list[FileReport]:
    """Scan all directories and collect per-file reports."""
    reports: list[FileReport] = []
    for scan_path in paths:
        if scan_path.is_file():
            report = scan_file(scan_path)
            if report is not None:
                reports.append(report)
        elif scan_path.is_dir():
            reports.extend(scan_directory(scan_path, threshold=0.0))
        else:
            msg = f"Warning: path does not exist: {scan_path}\n"
            sys.stderr.write(msg)
    return reports


def main() -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # Resolve scan directories.
    scan_paths = _resolve_test_dirs(args.path)
    if not scan_paths:
        msg = "No test directories found and none specified with --path.\n"
        sys.stderr.write(msg)
        return 1

    # Scan.
    reports = _collect_reports(scan_paths, args.threshold)
    sorted_reports = sorted(reports, key=lambda r: r.score, reverse=True)

    # Text output (pass all reports — filtering is internal to format_report).
    output = format_report(
        sorted_reports,
        threshold=args.threshold,
        top_n=args.top_n,
    )
    sys.stdout.write(output)
    sys.stdout.write("\n")

    # JSON output (optional).
    if args.json_path is not None:
        json_str = format_json(sorted_reports)
        args.json_path.write_text(json_str, encoding="utf-8")
        msg = f"JSON report written to {args.json_path}\n"
        sys.stderr.write(msg)

    # Fail-on check.
    if args.fail_on is not None:
        failing = [r for r in sorted_reports if r.score > args.fail_on]
        if failing:
            msg = (
                f"FAIL: {len(failing)} file(s) exceed score threshold "
                f"{args.fail_on:.2f}. Exiting with code 1.\n"
            )
            sys.stderr.write(msg)
            for report in failing:
                sys.stderr.write(
                    f"  {report.file_path}  (score={report.score:.2f}, "
                    f"{len(report.findings)} findings)\n"
                )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
