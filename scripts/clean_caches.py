#!/usr/bin/env python3
"""Clean all regenerable cache and artifact directories.

Removes build artifacts, cache directories, test outputs, and other
files that can be safely regenerated. Uses --dry-run to preview.

This file is the CLI entry point only (argument parsing, orchestration,
and reporting). The implementation is split across ``scripts/clean_cache_lib/``
to stay under the RULE-04 600-line script limit:

    clean_cache_lib/data.py     — CleanStats, Category, CATEGORIES,
                                  CATEGORY_GROUPS, EXCLUDED_ROOTS
    clean_cache_lib/ops.py      — exclusion/safety helpers, size
                                  formatting, category-name resolution
    clean_cache_lib/handlers.py — operation handlers, log cleanup,
                                  category orchestration

Design note: dry-run and real deletion share a SINGLE safe code path.
``_safe_rmtree`` / ``_safe_unlink`` (in ops.py) receive the ``dry_run``
flag and handle both modes internally, so the ``_is_excluded`` guard
runs identically in either mode. This prevents dry-run previews from
listing paths inside excluded roots such as ``.venv/``.

Categories:
  pycache           Python bytecode cache (__pycache__/, *.pyc)
  ruff              Ruff linter cache (.ruff_cache/)
  pytest            Pytest cache (.pytest_cache/)
  egg_info          Package egg-info directories (*.egg-info/)
  pyright           Pyright type checker cache (.pyright/, pyrightcache/)
  coverage          Coverage data and reports (.coverage, htmlcov/, etc.)
  node_modules      Node.js dependencies (node_modules/)
  next              Next.js build output (.next/, out/)
  turbo             Turborepo cache (.turbo/)
  tsbuildinfo       TypeScript incremental build info (*.tsbuildinfo)
  pnpm              pnpm store (.pnpm-store/)
  hypothesis        Hypothesis testing database (.hypothesis/)
  mutants           Mutation testing artifacts (mutants*/, symlinks, backups)
  logs              Log files (logs/, *.log at root)
  scratch           Scratch directory contents (_scratch/)
  tmp               Temporary files (.tmp/)
  ci                CI artifacts (.evidence/*.jsonl)
  dist              Build outputs (dist/, build/, .eggs/)
  frontend_reports  Frontend test reports (web/coverage/, playwright-report/,
                    test-results/)

Groups (expand to multiple categories for --include/--exclude):
  python_caches     ruff + pytest + egg_info + pyright
  frontend_all      next + turbo + tsbuildinfo + frontend_reports
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Make the sibling ``clean_cache_lib`` package importable when this script is
# run directly (``python scripts/clean_caches.py``). Inserted before the
# package imports below, hence the E402 exemptions.
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from clean_cache_lib import (  # noqa: E402
    CATEGORIES,
    CATEGORY_GROUPS,
    CATEGORY_INDEX,
    CleanStats,
    clean_category,
    expand_categories,
    format_size,
)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    category_names = sorted(CATEGORY_INDEX.keys())
    group_names = sorted(CATEGORY_GROUPS.keys())
    all_names = sorted(set(category_names + group_names))

    parser = argparse.ArgumentParser(
        description="Clean regenerable cache and artifact directories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Categories:\n"
            + "\n".join(f"  {c.name:<20s} {c.description}" for c in CATEGORIES)
            + "\n\nGroups:\n"
            + "\n".join(
                f"  {name:<20s} {', '.join(sorted(members))}"
                for name, members in CATEGORY_GROUPS.items()
            )
        ),
    )

    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print every path as it is removed",
    )
    parser.add_argument(
        "--size",
        "-s",
        action="store_true",
        help="Show disk space reclaimed per category",
    )
    parser.add_argument(
        "--exclude",
        metavar="CATEGORY",
        action="append",
        default=[],
        choices=all_names,
        help=f"Skip a category or group. Choices: {', '.join(all_names)}",
    )
    parser.add_argument(
        "--include",
        metavar="CATEGORY",
        action="append",
        default=[],
        choices=all_names,
        help=f"Only clean specified categories/groups. Choices: {', '.join(all_names)}",
    )
    parser.add_argument(
        "--keep-logs",
        metavar="N",
        type=int,
        default=0,
        help="Keep the N most recent log files per service (default: 0 = delete all)",
    )

    return parser


def _print_summary(
    total: CleanStats,
    start_time: float,
    categories_processed: int,
    size_mode: bool,
    dry_run: bool,
) -> None:
    """Print a one-line summary of what was cleaned."""
    prefix = "[DRY-RUN] " if dry_run else ""
    parts = [
        f"{prefix}Cleaned {total.paths_removed} paths across {categories_processed} categories"
    ]
    if size_mode:
        parts.append(f"({format_size(total.bytes_freed)} freed)")
    elapsed = time.monotonic() - start_time
    parts.append(f"in {elapsed:.2f}s")
    if total.errors:
        parts.append(f"with {total.errors} error(s)")
    print(" ".join(parts))


def main() -> int:
    """Entry point. Returns 0 on success, 1 on error."""
    parser = _build_parser()
    args = parser.parse_args()

    # Resolve active categories
    active_names = expand_categories(args.include) if args.include else set(CATEGORY_INDEX)

    excluded_names = expand_categories(args.exclude)
    active_names -= excluded_names

    if not active_names:
        print("No categories selected. Nothing to do.")
        return 0

    # Sort for deterministic output order
    ordered_categories = [c for c in CATEGORIES if c.name in active_names]

    start = time.monotonic()
    total_stats = CleanStats()
    size_mode = args.size or args.verbose  # Track sizes for verbose summary too

    for cat in ordered_categories:
        stats = clean_category(
            cat,
            dry_run=args.dry_run,
            verbose=args.verbose,
            track_size=size_mode,
            keep_logs=args.keep_logs,
        )
        total_stats += stats

        if args.size and stats.paths_removed > 0:
            label = f"{cat.name}: {stats.paths_removed} item(s)"
            if stats.bytes_freed:
                label += f", {format_size(stats.bytes_freed)}"
            if stats.errors:
                label += f", {stats.errors} error(s)"
            print(f"  {label}")

    _print_summary(
        total=total_stats,
        start_time=start,
        categories_processed=len(ordered_categories),
        size_mode=size_mode,
        dry_run=args.dry_run,
    )

    return 1 if total_stats.errors else 0


if __name__ == "__main__":
    sys.exit(main())
