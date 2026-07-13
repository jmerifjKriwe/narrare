#!/usr/bin/env python3
"""No-growth gate for hardcoded empty KB context variable assignments.

Detects service code that declares a KB variable (e.g. ``"kb_characters": ""``)
but hardcodes it to an empty string at runtime. This gap — a variable present
in the template but empty at call time — caused the Coreference-class adoption
bug (CR-AUFG-03-02/03-09). The scorer checks template *presence* statically;
this checker scans service code for empty assignments that defeat that check.

Existing violations are ratcheted by baseline; new ones fail the gate.

Usage:
    python scripts/check_empty_kb_vars.py               # ratcheted check
    python scripts/check_empty_kb_vars.py --baseline X   # custom baseline
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.architecture.baselines import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    compare_section,
    format_comparison,
    stable_fingerprint,
)

EMPTY_KB_VAR_SECTION = "empty_kb_vars"
SCAN_ROOT = ROOT / "apps" / "api" / "narrare"

# Known KB context variables that may be declared but emptied at runtime.
KB_VARS = frozenset({"kb_characters", "kb_locations", "kb_factions", "kb_relationships"})

# Matches: "kb_characters": ""  (flexible whitespace around colon).
EMPTY_KB_VAR_RE = re.compile(
    r'"(kb_characters|kb_locations|kb_factions|kb_relationships)"\s*:\s*""'
)

# Directory parts that indicate non-production code.
_IGNORED_PARTS: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".venv",
        ".git",
        "node_modules",
        ".pytest_cache",
        "_scratch",
    }
)

# Path fragments indicating auto-generated or migration content.
_SKIP_PATH_FRAGMENTS: frozenset[str] = frozenset(
    {
        "alembic/versions",
        "alembic\\versions",
    }
)


def _should_skip(path: Path) -> bool:
    """Return True if the file should be excluded from scanning.

    Excludes test files (``test_*.py``, ``*_test.py``, ``*_test_helpers.py``),
    ``__pycache__``, virtualenvs, and migration files.
    """
    name = path.name

    # Exclude test files.
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py") or name.endswith("_test_helpers.py"):
        return True

    # Exclude __pycache__, .venv, etc.
    if any(part in _IGNORED_PARTS for part in path.parts):
        return True

    # Exclude migration files.
    return any(frag in path.as_posix() for frag in _SKIP_PATH_FRAGMENTS)


def collect_empty_kb_vars(
    scan_root: Path = SCAN_ROOT,
    repo_root: Path = ROOT,
) -> set[str]:
    """Collect fingerprints of hardcoded empty KB variable assignments.

    Scans ``*.py`` files under *scan_root* (excluding tests, pycache,
    migrations) for patterns like ``"kb_characters": ""``. Returns a set of
    stable fingerprints in the form ``"<repo-relative-path> | <var-name>"``.
    """
    findings: set[str] = set()
    if not scan_root.is_dir():
        return findings

    # Compute the repo-relative prefix (e.g. "apps/api/narrare/").
    try:
        prefix = scan_root.relative_to(repo_root)
    except ValueError:
        prefix = Path()

    for path in sorted(scan_root.rglob("*.py")):
        if _should_skip(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            rel = (prefix / path.relative_to(scan_root)).as_posix()
        except ValueError:
            rel = path.as_posix()
        for match in EMPTY_KB_VAR_RE.finditer(text):
            var_name = match.group(1)
            findings.add(stable_fingerprint(rel, var_name))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="No-growth gate for empty KB variable assignments.",
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--scan-root", type=Path, default=SCAN_ROOT)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()

    findings = collect_empty_kb_vars(args.scan_root, args.repo_root)
    comparison = compare_section(findings, EMPTY_KB_VAR_SECTION, args.baseline)
    print(format_comparison(comparison, "Empty KB variable assignments"))
    if comparison.ok:
        print("RESULT: No new empty KB variable assignments")
        return 0
    print("RESULT: New empty KB variable assignment(s) require baseline update")
    return 1


if __name__ == "__main__":
    sys.exit(main())
