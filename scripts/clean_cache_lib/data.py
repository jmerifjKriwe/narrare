"""Data structures and category definitions for clean_caches.

This module is an implementation detail of ``scripts/clean_caches.py`` and
exists solely to keep the entry point under the RULE-04 600-line script limit.
It holds the immutable data declarations (stats dataclass, category catalog,
excluded roots, category groups) while the operations live in ``ops.py``.

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

from dataclasses import dataclass
from pathlib import Path

# Project root (this file is at scripts/clean_cache_lib/data.py → three parents up)
ROOT: Path = Path(__file__).resolve().parent.parent.parent

# Directories that should never be cleaned (expensive or tracked content).
# The safety check (_is_excluded in ops.py) matches the FIRST path component
# against this set, so any nested path inside one of these roots is protected.
EXCLUDED_ROOTS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        ".code-review-graph",
        ".superpowers",
        ".opencode",
        ".agents",
        "_audit",
    }
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CleanStats:
    """Accumulated cleaning statistics for one category."""

    paths_removed: int = 0
    bytes_freed: int = 0
    errors: int = 0

    def __add__(self, other: CleanStats) -> CleanStats:
        return CleanStats(
            self.paths_removed + other.paths_removed,
            self.bytes_freed + other.bytes_freed,
            self.errors + other.errors,
        )

    def __iadd__(self, other: CleanStats) -> CleanStats:
        self.paths_removed += other.paths_removed
        self.bytes_freed += other.bytes_freed
        self.errors += other.errors
        return self


@dataclass
class Category:
    """A cleanable category with a name, description, and operations.

    Each operation is a (kind, target) tuple:
      ("glob_dir", glob_pattern)  — find directories by glob, rmtree each
      ("glob_file", glob_pattern) — find files by glob, unlink each
      ("path_dir", rel_path)      — delete a specific directory at rel_path
      ("path_file", rel_path)     — delete a specific file at rel_path
      ("empty_dir", rel_path)     — remove all contents of a directory, keep dir
    """

    name: str
    description: str
    ops: list[tuple[str, str]]


CATEGORIES: list[Category] = [
    Category(
        "pycache",
        "Python bytecode cache",
        [
            ("glob_dir", "**/__pycache__"),
            ("glob_file", "**/*.pyc"),
        ],
    ),
    Category(
        "ruff",
        "Ruff linter cache",
        [
            ("glob_dir", "**/.ruff_cache"),
        ],
    ),
    Category(
        "pytest",
        "Pytest cache",
        [
            ("glob_dir", "**/.pytest_cache"),
        ],
    ),
    Category(
        "egg_info",
        "Package egg-info directories",
        [
            ("glob_dir", "**/*.egg-info"),
        ],
    ),
    Category(
        "pyright",
        "Pyright type checker cache",
        [
            ("glob_dir", "**/.pyright"),
            ("glob_dir", "**/pyrightcache"),
        ],
    ),
    Category(
        "coverage",
        "Coverage data and reports",
        [
            ("glob_file", ".coverage"),
            ("glob_file", ".coverage.*"),
            ("glob_file", "coverage*.xml"),
            ("glob_file", "*,cover"),
            ("glob_dir", "**/htmlcov"),
        ],
    ),
    Category(
        "node_modules",
        "Node.js dependencies",
        [
            ("glob_dir", "**/node_modules"),
        ],
    ),
    Category(
        "next",
        "Next.js build output",
        [
            ("path_dir", "packages/web/.next"),
            ("path_dir", "packages/web/out"),
        ],
    ),
    Category(
        "turbo",
        "Turborepo cache",
        [
            ("path_dir", "packages/web/.turbo"),
        ],
    ),
    Category(
        "tsbuildinfo",
        "TypeScript incremental build info files",
        [
            ("glob_file", "**/*.tsbuildinfo"),
        ],
    ),
    Category(
        "pnpm",
        "pnpm store",
        [
            ("path_dir", ".pnpm-store"),
        ],
    ),
    Category(
        "hypothesis",
        "Hypothesis testing cache",
        [
            ("path_dir", ".hypothesis"),
        ],
    ),
    Category(
        "mutants",
        "Mutation testing artifacts",
        [
            ("glob_dir", "mutants*"),
            ("glob_dir", "**/mutants*"),
            ("path_file", ".mutmut.pyproject.toml.bak"),
            ("path_file", "narrare_core"),
            ("path_file", "narrare"),
        ],
    ),
    Category(
        "logs",
        "Log files",
        [
            # Handled separately via _clean_logs() for --keep-logs support
        ],
    ),
    Category(
        "scratch",
        "Scratch directory contents",
        [
            ("empty_dir", "_scratch"),
        ],
    ),
    Category(
        "tmp",
        "Temporary files",
        [
            ("path_dir", ".tmp"),
        ],
    ),
    Category(
        "ci",
        "CI artifacts",
        [
            ("glob_file", ".evidence/*.jsonl"),
        ],
    ),
    Category(
        "dist",
        "Build outputs",
        [
            ("glob_dir", "dist"),
            ("glob_dir", "build"),
            ("glob_dir", ".eggs"),
        ],
    ),
    Category(
        "frontend_reports",
        "Frontend test coverage and reports",
        [
            ("path_dir", "packages/web/coverage"),
            ("path_dir", "packages/web/playwright-report"),
            ("path_dir", "packages/web/test-results"),
        ],
    ),
]

CATEGORY_INDEX: dict[str, Category] = {c.name: c for c in CATEGORIES}

# Groups expand to multiple category names for --include/--exclude.
# Note: group names must differ from category names to avoid ambiguity —
# "frontend_all" groups all frontend-related categories, while
# "frontend_reports" remains a standalone category.
CATEGORY_GROUPS: dict[str, set[str]] = {
    "python_caches": {"ruff", "pytest", "egg_info", "pyright"},
    "frontend_all": {"next", "turbo", "tsbuildinfo", "frontend_reports"},
}
