#!/usr/bin/env python3
"""
Narrare Architecture Constraint Checker.

Enforces the rules defined in CONSTRAINTS.md.
Reads configuration from pyproject.toml [tool.narrare.architecture].

Exit code 0: all constraints pass.
Exit code 1: violations found.

See: docs/_shared/CONSTRAINTS.md
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so `scripts.architecture` resolves
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.architecture.checkers import scan_file  # noqa: E402
from scripts.architecture.helpers import ROOT, load_config  # noqa: E402
from scripts.architecture.types import CheckResult, Violation  # noqa: E402


def check_forbidden_files(result: CheckResult) -> None:
    """RULE-15: No middleware.ts in packages/web/.

    Next.js 16+ uses proxy.ts exclusively. The build breaks if both exist.
    See: docs/_shared/CONSTRAINTS.md
    """
    forbidden_patterns = {
        "middleware.ts": "packages/web",
    }
    for filename, search_dir in forbidden_patterns.items():
        search_path = ROOT / search_dir
        if not search_path.exists():
            continue
        for match in search_path.rglob(filename):
            result.violations.append(
                Violation(
                    file=match,
                    line=0,
                    rule="RULE-15",
                    detail=(
                        f"Forbidden file '{filename}' found. "
                        f"Next.js 16+ uses proxy.ts exclusively. "
                        f"See RULE-15 in docs/_shared/CONSTRAINTS.md."
                    ),
                )
            )


def main() -> int:
    config = load_config()
    result = CheckResult()

    # RULE-15: Check for forbidden files before scanning Python sources
    check_forbidden_files(result)

    scan_roots = [ROOT / "apps", ROOT / "packages", ROOT / "scripts", ROOT / "tests"]
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for py_file in scan_root.rglob("*.py"):
            scan_file(py_file, config, result)

    # Report approved exceptions (visible in CI for review)
    if result.approved_exceptions:
        print("\n⚠️  Approved exceptions (require review in PR):\n")
        for v in result.approved_exceptions:
            print(f"  {v.file}:{v.line}  [{v.rule}]  {v.detail}")
            if v.approval_reason:
                print(f"    → Reason: {v.approval_reason}")

    # Report violations
    if result.violations:
        print("\n❌ Architecture violations found:\n")
        for v in sorted(result.violations, key=lambda x: (str(x.file), x.line)):
            print(f"  {v.file}:{v.line}  [{v.rule}]  {v.detail}")
        print(
            f"\n{len(result.violations)} violation(s) in {result.files_checked} files. Aborting.\n"
        )
        print("See docs/_shared/CONSTRAINTS.md for rules.\n")
        return 1

    print(
        f"✅ Architecture constraints OK "
        f"({result.files_checked} files checked"
        + (
            f", {len(result.approved_exceptions)} approved exception(s)"
            if result.approved_exceptions
            else ""
        )
        + ")"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
