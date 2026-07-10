#!/usr/bin/env python3
"""
Narrare Architecture Constraint Checker.

Enforces the rules defined in CONSTRAINTS.md.
Reads configuration from pyproject.toml [tool.narrare.architecture].

Exit code 0: all constraints pass.
Exit code 1: violations found.

Use ``--list-rules`` to print the enforced RULE-XX identifiers (the
authoritative self-report — docs should reference this rather than
maintaining separate rule lists that drift).

See: docs/_shared/CONSTRAINTS.md
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so `scripts.architecture` resolves
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import argparse  # noqa: E402

from scripts.architecture.checkers import scan_file  # noqa: E402
from scripts.architecture.helpers import ROOT, load_config  # noqa: E402
from scripts.architecture.types import CheckResult, Violation  # noqa: E402

# ── Enforced rules (self-report) ────────────────────────────────
#
# This constant is the authoritative list of RULE-XX identifiers enforced
# by the base checker (without --prompt-integrity). Docs should reference
# ``--list-rules`` or this constant rather than maintaining separate lists.
# When a new rule is added to the checkers, update this constant too.

ENFORCED_RULES: tuple[str, ...] = (
    "RULE-01b",  # LLM imports — no direct openai outside core/llm/
    "RULE-02",  # Prompt building — only in core/prompts/
    "RULE-04",  # File size limits — modularize, don't compress
    "RULE-07",  # Import direction — no core → apps imports
    "RULE-11",  # Silent failures — no bare except, no silent swallow
    "RULE-15",  # Forbidden files — no middleware.ts in packages/web/
    "RULE-18",  # Router config — no hardcoded constants
    "RULE-19",  # Model config — no hardcoded model strings
)

# Additional rules enforced only with --prompt-integrity flag.
PROMPT_INTEGRITY_RULES: tuple[str, ...] = (
    "RULE-02a",  # Prompt content categories (ADR-026)
    "RULE-02b",  # Prompt resolution path (ADR-046)
)


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


def run_prompt_integrity_checks(result: CheckResult) -> None:
    """Run all prompt integrity checks (--prompt-integrity flag)."""
    try:
        from scripts.architecture._checkers.prompt_integrity import run_all_checks

        run_all_checks(result)
    except ImportError as exc:
        result.approved_exceptions.append(
            Violation(
                file=Path("scripts/check_architecture.py"),
                line=0,
                rule="PROMPT-INTEGRITY",
                detail=f"Prompt integrity checks not available (import error: {exc})",
                approved=True,
                approval_reason="Dependency not installed",
            )
        )


def _print_enforced_rules() -> None:
    """Print the enforced RULE-XX identifiers (self-report)."""
    print("Enforced rules (base checker):")
    for rule in ENFORCED_RULES:
        print(f"  {rule}")
    print()
    print("Additional rules with --prompt-integrity:")
    for rule in PROMPT_INTEGRITY_RULES:
        print(f"  {rule}")
    print()
    print("See docs/_shared/CONSTRAINTS.md for full rule definitions.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Narrare Architecture Constraint Checker")
    parser.add_argument(
        "--prompt-integrity",
        action="store_true",
        help="Run additional prompt integrity checks (variable registration, "
        "i18n parity, intent consistency, variable usage)",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="Print the enforced RULE-XX identifiers and exit.",
    )
    args = parser.parse_args()

    if args.list_rules:
        _print_enforced_rules()
        return 0

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

    # Prompt integrity checks (--prompt-integrity flag)
    if args.prompt_integrity:
        run_prompt_integrity_checks(result)

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
