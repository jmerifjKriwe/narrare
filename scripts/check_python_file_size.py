#!/usr/bin/env python3
"""RULE-04 Python file-size gate.

Enforces hard line-count limits per file category as defined in
CONSTRAINTS.md §1 RULE-04. Existing violations are ratcheted by baseline;
new oversized files fail the gate and must be modularized.

Categories and limits (from CONSTRAINTS.md):
    - General Python module:  400 lines hard limit
    - Router (router*.py):    150 lines
    - Dependency (deps.py, dependencies.py, deps_*.py): 200 lines
    - Service (service.py, *_service.py): 300 lines
    - Agent (*_agent.py, agent.py): 200 lines
    - Config/schema (config.py, schemas.py, *_schemas.py): 200 lines
    - Test (test_*.py): 400 lines
    - Scripts (scripts/): 600 lines
    - Models (models.py): 500 lines (data declarations are inherently long)

Usage:
    python scripts/check_python_file_size.py              # ratcheted baseline check
    python scripts/check_python_file_size.py --no-baseline # fail on any violation
    python scripts/check_python_file_size.py --json        # machine-readable output
    python scripts/check_python_file_size.py --update-baseline  # write current state to baseline
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.architecture.baselines import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    compare_section,
    format_comparison,
    stable_fingerprint,
)

PYTHON_FILE_SIZE_BASELINE_SECTION = "python_file_size_violations"

# Directories/patterns to always skip.
_IGNORED_PARTS: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".venv",
        ".git",
        "node_modules",
        ".next",
        "dist",
        "htmlcov",
        ".pytest_cache",
        "_scratch",
    }
)

# Exact filenames to always skip (relative to scan root or any subdirectory).
_ALWAYS_SKIP_NAMES: frozenset[str] = frozenset(
    {
        "__init__.py",
    }
)

# Directory path fragments that indicate auto-generated or migration content.
_SKIP_PATH_FRAGMENTS: frozenset[str] = frozenset(
    {
        "alembic/versions",
        "alembic\\versions",
    }
)


def _display_path(path: Path, base: Path = ROOT) -> Path:
    """Return a stable display path, tolerating synthetic test paths."""
    try:
        return path.relative_to(base)
    except ValueError:
        return Path(path.as_posix())


@dataclass(frozen=True)
class FileSizeViolation:
    """A Python file above its configured hard limit."""

    path: Path
    lines: int
    limit: int
    kind: str

    def fingerprint(self) -> str:
        """Stable baseline key; excludes line count so debt can shrink freely."""
        return stable_fingerprint(self.path.as_posix(), self.kind, self.limit)


def _limit_for(path: Path, root: Path = ROOT) -> tuple[str, int]:
    """Determine the file category and hard line-count limit.

    Priority order (first match wins):
    1. Test files
    2. Scripts
    3. Router files
    4. Dependency files
    5. Service files
    6. Agent files
    7. Config/schema files
    8. Models
    9. General Python
    """
    name = path.name
    rel = _display_path(path, root)
    rel_str = rel.as_posix()

    # Test files: test_*.py
    if name.startswith("test_") and name.endswith(".py"):
        return "test", 400

    # Scripts directory gets higher limit (tooling is inherently longer)
    if rel_str.startswith("scripts/"):
        return "script", 600

    # Router files: router.py, router_*.py
    if name == "router.py" or name.startswith("router_"):
        return "router", 150

    # Dependency files: dependencies.py, deps.py, deps_*.py
    if name in ("dependencies.py", "deps.py") or name.startswith("deps_"):
        return "dependency", 200

    # Service files: service.py, *_service.py
    if name == "service.py" or name.endswith("_service.py"):
        return "service", 300

    # Agent files: agent.py, *_agent.py
    if name == "agent.py" or name.endswith("_agent.py"):
        return "agent", 200

    # Config/schema files: config.py, schemas.py, *_schemas.py, settings.py
    if name in ("config.py", "schemas.py", "settings.py") or name.endswith("_schemas.py"):
        return "config_schema", 200

    # Models: models.py (data declarations are inherently verbose)
    if name == "models.py":
        return "models", 500

    # General Python module
    return "general", 400


def _count_lines(path: Path) -> int:
    """Count total lines in a file (including blank lines and comments).

    RULE-04 explicitly forbids deleting comments/blank lines to squeeze
    under the limit, so we count the real file size.
    """
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


def _should_skip(path: Path, root: Path = ROOT) -> bool:
    """Check if a file should be excluded from size checking."""
    # Skip by filename
    if path.name in _ALWAYS_SKIP_NAMES:
        return True

    # Skip by directory part
    if any(part in _IGNORED_PARTS for part in path.parts):
        return True

    # Skip auto-generated / migration directories
    rel_str = _display_path(path, root).as_posix()
    return any(frag in rel_str for frag in _SKIP_PATH_FRAGMENTS)


def _iter_python_sources(root: Path = ROOT) -> list[Path]:
    """Collect all .py files that should be checked."""
    files: list[Path] = []
    scan_dirs: list[Path] = []

    # Scan these top-level directories if they exist
    candidates = [
        root / "apps",
        root / "packages",
        root / "scripts",
        root / "tests",
        root / "evals",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            scan_dirs.append(candidate)

    # Also scan standalone .py files at the root (like conftest.py)
    for path in root.glob("*.py"):
        if not _should_skip(path, root):
            files.append(path)

    for scan_dir in scan_dirs:
        for path in scan_dir.rglob("*.py"):
            if not _should_skip(path, root):
                files.append(path)

    return sorted(set(files))


def collect_violations(root: Path = ROOT) -> list[FileSizeViolation]:
    """Collect Python files exceeding RULE-04 hard limits."""
    violations: list[FileSizeViolation] = []
    for path in _iter_python_sources(root):
        kind, limit = _limit_for(path, root)
        lines = _count_lines(path)
        if lines > limit:
            violations.append(
                FileSizeViolation(
                    path=_display_path(path, root),
                    lines=lines,
                    limit=limit,
                    kind=kind,
                )
            )
    return violations


def format_report(violations: list[FileSizeViolation]) -> str:
    """Format a human-readable file-size report."""
    lines = ["Python RULE-04 file-size check", "=" * 34]
    if not violations:
        lines.append("✅ All Python files are within hard limits")
        return "\n".join(lines)
    for violation in sorted(violations, key=lambda item: (-item.lines, item.path.as_posix())):
        lines.append(
            f"WARN: {violation.path} has {violation.lines} lines "
            f"({violation.kind} hard limit: {violation.limit})"
        )
    return "\n".join(lines)


def format_json(violations: list[FileSizeViolation]) -> str:
    """Format findings as machine-readable JSON."""
    return json.dumps(
        [
            {
                "path": item.path.as_posix(),
                "lines": item.lines,
                "limit": item.limit,
                "kind": item.kind,
                "fingerprint": item.fingerprint(),
            }
            for item in violations
        ],
        indent=2,
    )


def update_baseline(
    violations: list[FileSizeViolation],
    baseline_path: Path = DEFAULT_BASELINE_PATH,
) -> None:
    """Write current violations as the new baseline section."""
    from typing import Any, cast

    baseline: dict[str, Any] = {}
    if baseline_path.exists():
        with baseline_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                baseline = cast("dict[str, Any]", data)

    fingerprints = sorted(item.fingerprint() for item in violations)
    baseline[PYTHON_FILE_SIZE_BASELINE_SECTION] = fingerprints

    with baseline_path.open("w", encoding="utf-8") as fh:
        json.dump(baseline, fh, indent=2, sort_keys=False)
        fh.write("\n")

    print(f"Updated baseline: {len(fingerprints)} violations recorded in {baseline_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Python file-size limits (RULE-04).",
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="Project root directory")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument(
        "--no-baseline", action="store_true", help="Fail on any violation (ignore baseline)"
    )
    parser.add_argument(
        "--update-baseline", action="store_true", help="Write current violations as new baseline"
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = parser.parse_args()

    violations = collect_violations(args.root)

    if args.json:
        print(format_json(violations))
    else:
        print(format_report(violations))

    # Baseline update mode: write and exit successfully
    if args.update_baseline:
        update_baseline(violations, args.baseline)
        return 0

    # No-baseline mode: fail on any violation
    if args.no_baseline:
        return 1 if violations else 0

    # Default: ratcheted baseline comparison
    comparison = compare_section(
        {item.fingerprint() for item in violations},
        PYTHON_FILE_SIZE_BASELINE_SECTION,
        args.baseline,
    )
    print(format_comparison(comparison, "Python file-size ratchet"))
    if comparison.ok:
        print("RESULT: Python file-size debt did not grow")
        return 0
    print("RESULT: New Python hard-limit violation(s) require modularization")
    return 1


if __name__ == "__main__":
    sys.exit(main())
