"""CLI entry point for test coverage gap analysis.

Provides argument parsing and the main orchestration function that
ties together source discovery, test file mapping, and reporting.

See: docs/_shared/CONSTRAINTS.md (RULE-10)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .discovery import (
    DEFAULT_TEST_ROOT,
    REPO_ROOT,
    SOURCE_SCAN_DIRS,
    AnalysisConfig,
    SourceFile,
    count_public_methods,
    count_test_functions,
    discover_source_files,
)
from .mapping import find_test_files
from .reporting import format_json, format_report


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Check that service/repository files have corresponding test files (RULE-10)."
        ),
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        action="append",
        default=None,
        help=("Additional source directories to scan (can be repeated). Auto-detected if omitted."),
    )
    parser.add_argument(
        "--test-dir",
        type=Path,
        default=DEFAULT_TEST_ROOT,
        help=(
            f"Root directory for unit tests (default: {DEFAULT_TEST_ROOT.relative_to(REPO_ROOT)})"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Exit with code 1 if any source file has no test file",
    )
    parser.add_argument(
        "--fail-on-low",
        action="store_true",
        help="Exit with code 2 if any source file has low test-to-method ratio",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Minimum test-to-method ratio (default: 0.5)",
    )
    return parser


def _analyze(
    source_dirs: list[tuple[Path, str]] | None = None,
    config: AnalysisConfig | None = None,
) -> list[SourceFile]:
    """Run the full analysis and return results for each source file."""
    if config is None:
        config = AnalysisConfig()

    files = discover_source_files(source_dirs, config)

    for source in files:
        source.public_methods = count_public_methods(source.path)
        source.test_files = find_test_files(source)
        source.test_functions = sum(count_test_functions(tf) for tf in source.test_files)

    return files


def main() -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    config = AnalysisConfig(
        test_root=args.test_dir,
        threshold=args.threshold,
    )

    # Build source dirs list.
    source_dirs: list[tuple[Path, str]] = list(SOURCE_SCAN_DIRS)
    if args.source_dir is not None:
        for extra in args.source_dir:
            resolved = extra.resolve()
            # Auto-detect layer from path.
            layer = "core" if "narrare_core" in str(resolved) else "api"
            source_dirs.append((resolved, layer))

    # Run analysis.
    results = _analyze(source_dirs=source_dirs, config=config)

    # Output.
    if args.json_output:
        print(format_json(results))
    else:
        print(format_report(results))

    # Exit codes.
    missing = [r for r in results if r.status == "missing"]
    low = [r for r in results if r.status == "low"]

    if args.fail_on_missing and missing:
        print(
            f"\n::error::{len(missing)} source file(s) have no test file. See output above.",
            file=sys.stderr,
        )
        return 1

    if args.fail_on_low and low:
        print(
            f"\n::warning::{len(low)} source file(s) have low test coverage "
            f"(below {args.threshold:.0%}). See output above.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
