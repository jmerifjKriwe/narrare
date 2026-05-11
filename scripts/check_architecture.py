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
from scripts.architecture.types import CheckResult  # noqa: E402


def main() -> int:
    config = load_config()
    result = CheckResult()

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
