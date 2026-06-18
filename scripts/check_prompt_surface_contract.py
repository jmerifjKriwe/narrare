#!/usr/bin/env python3
"""
Narrare Prompt Surface Contract Checker — CI script.

Runs all prompt-surface contract checks against the real repository:
- ADR-037 / INFRA-012: manifest coverage, route/template drift, variables,
  XML wrapping, generated-candidate labelling, production inline fallback.
- ADR-049 Phase D: prompt-identity chain (A1), root-mode prohibition (A2),
  path derivability (A3), frontmatter match (A4), context-modes (D11),
  orphan templates (A6), inline feature-prompt (A5), ADR-status consistency (D8).

Exit codes:
    0: All prompt-surface checks pass.
    1: One or more violations found.

Usage:
    python scripts/check_prompt_surface_contract.py
    python scripts/check_prompt_surface_contract.py --verbose

See:
    - docs/architecture/decisions/ADR-037-prompt-surface-contract-manifest.md
    - docs/architecture/decisions/ADR-049-prompt-surface-identity-path-contract.md
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# Ensure project root is on sys.path so `scripts.architecture` resolves.
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.architecture._checkers._check_adr_status_consistency import (  # noqa: E402
    check_adr_status_consistency,
)
from scripts.architecture._checkers._check_inline_feature_prompt import (  # noqa: E402
    check_inline_feature_prompt,
)
from scripts.architecture._checkers._check_prompt_identity import (  # noqa: E402
    check_prompt_identity,
)
from scripts.architecture._checkers._check_prompt_surface import check_prompt_surface  # noqa: E402
from scripts.architecture.helpers import relative_to_root  # noqa: E402
from scripts.architecture.types import CheckResult  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _run_inline_feature_prompt_scan(result: CheckResult) -> None:
    """Scan apps/api Python files for A5 inline feature-prompt violations."""
    api_dir = ROOT / "apps" / "api"
    if not api_dir.is_dir():
        return

    for py_file in api_dir.rglob("*.py"):
        if any(part in str(py_file) for part in [".venv", "__pycache__", "migrations"]):
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue

        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        rel_path = relative_to_root(py_file)
        violations = check_inline_feature_prompt(rel_path, tree, source.splitlines())
        for v in violations:
            if v.approved:
                result.approved_exceptions.append(v)
            else:
                result.violations.append(v)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Narrare Prompt Surface Contract Checker (ADR-037 + ADR-049)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show approved exceptions in addition to violations",
    )
    args = parser.parse_args()

    result = CheckResult()

    # --- ADR-037: existing prompt-surface manifest gates ---
    check_prompt_surface(result, root=ROOT)

    # --- ADR-049 Phase D: identity/path gates ---
    check_prompt_identity(result, root=ROOT)

    # --- ADR-049 Phase D A5: inline feature-prompt (per-file AST scan) ---
    _run_inline_feature_prompt_scan(result)

    # --- ADR-049 Phase D D8: ADR-status consistency ---
    check_adr_status_consistency(result, root=ROOT)

    # --- Report ---
    if result.approved_exceptions and args.verbose:
        print("\n⚠️  Approved exceptions (require review in PR):\n")
        for v in result.approved_exceptions:
            print(f"  {v.file}:{v.line}  [{v.rule}]  {v.detail}")
            if v.approval_reason:
                print(f"    → Reason: {v.approval_reason}")

    if result.violations:
        print("\n❌ Prompt Surface Contract violations found:\n")
        for v in sorted(result.violations, key=lambda x: (str(x.file), x.line)):
            print(f"  {v.file}:{v.line}  [{v.rule}]  {v.detail}")
        print(
            f"\n{len(result.violations)} violation(s) found. See ADR-037 / ADR-049 for details.\n"
        )
        return 1

    parts = ["✅ Prompt Surface Contract OK"]
    if result.approved_exceptions:
        parts.append(f"({len(result.approved_exceptions)} approved exception(s))")
    print(" ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
