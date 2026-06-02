#!/usr/bin/env python3
"""
Narrare Prompt Structure Validator.

Validates all prompt files in packages/core/narrare_core/prompts/_bundled/
for structural consistency, variable safety, and locale sync.

Checks:
  1. YAML frontmatter validation (prompt_type, prompt_language, prompt_version)
  2. Required sections (System Prompt, Output Format, Do NOT)
  3. Variable consistency across locales
  4. Security: user-content variables must be wrapped in XML tags
  5. File size check (max 300 lines per prompt file)
  6. Locale coverage (all modes should exist in EN, DE, FR)
  7. Meta-prompt guardrails (ADR-019 mandatory elements)
  8. Universal rules presence (files exist with key phrases)
  9. No universal rules duplication in templates

Exit codes:
  0: All checks pass (warnings OK)
  1: One or more FAIL-level issues found
  2 (with --strict): Warnings treated as failures

Usage:
  python scripts/check_prompt_structure.py
  python scripts/check_prompt_structure.py --strict
  python scripts/check_prompt_structure.py --help
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow importing from the same directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prompt_checks import (
    Issue,
    check_file_size,
    check_frontmatter,
    check_required_sections,
    check_security,
    check_variable_consistency,
)
from prompt_checks_crossfile import (
    check_locale_coverage,
    check_meta_guardrails,
    discover_prompts,
)
from prompt_checks_universal import (
    check_no_universal_rules_in_templates,
    check_universal_rules_presence,
)

# ── Constants ──────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
BUNDLED_DIR = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"


# ── Reporting ──────────────────────────────────────────────────


def print_report(
    total: int,
    system_count: int,
    issues: list[Issue],
    strict: bool,
) -> int:
    """Print a summary report and return exit code."""
    fails = [i for i in issues if i.level == "FAIL"]
    warns = [i for i in issues if i.level == "WARN"]

    fail_files: set[str] = {i.file_path for i in fails}
    warn_files: set[str] = {i.file_path for i in warns}
    clean_count = system_count - len(fail_files | warn_files)

    print()
    if clean_count == system_count and not fails:
        print(f"PASS: {system_count}/{system_count} system prompts valid")
    elif not fails:
        print(
            f"PASS: {clean_count}/{system_count} system prompts valid "
            f"({len(warn_files)} with warnings)"
        )
    else:
        print(
            f"PASS: {clean_count}/{system_count} system prompts valid "
            f"({len(fail_files)} failed, {len(warn_files)} warned)"
        )

    for w in sorted(warns, key=lambda i: i.file_path):
        print(f"WARN: {w.file_path} — {w.message}")

    for f in sorted(fails, key=lambda i: i.file_path):
        print(f"FAIL: {f.file_path} — {f.message}")

    non_system = total - system_count
    if non_system:
        print(f"INFO: {non_system} non-system .md files skipped (tones, name-styles, etc.)")

    print()

    if fails:
        print(f"RESULT: {len(fails)} FAIL(s), {len(warns)} WARN(s)")
        return 1

    if strict and warns:
        print(f"RESULT: {len(warns)} WARN(s) treated as FAIL(s) (--strict mode)")
        return 1

    if warns:
        print(f"RESULT: {len(warns)} WARN(s) (non-blocking)")
    else:
        print("RESULT: All checks passed")

    return 0


# ── Main ───────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Narrare prompt file structure and quality.",
        epilog=(
            "Run from project root. Validates files under "
            "packages/core/narrare_core/prompts/_bundled/."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures (non-zero exit code).",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=BUNDLED_DIR,
        help="Path to _bundled/ directory (default: auto-detected).",
    )
    args = parser.parse_args()

    bundled_dir = args.path
    if not bundled_dir.is_dir():
        print(
            f"ERROR: Prompt directory not found: {bundled_dir}",
            file=sys.stderr,
        )
        return 1

    # Discover all prompt files.
    prompts = discover_prompts(bundled_dir)
    total = len(prompts)
    system_prompts = [p for p in prompts if p.is_system_md]
    system_count = len(system_prompts)

    if total == 0:
        print("WARN: No .md files found in bundled prompts directory.")
        return 0

    issues: list[Issue] = []

    # Run all checks.
    for pf in prompts:
        check_frontmatter(pf, issues)
        check_required_sections(pf, issues)
        check_security(pf, issues)
        check_file_size(pf, issues)

    # Cross-file check: variable consistency.
    check_variable_consistency(prompts, issues)

    # Cross-file checks: locale coverage and meta-prompt guardrails.
    check_locale_coverage(prompts, issues)
    check_meta_guardrails(prompts, issues)

    # Universal rules: presence and duplication checks.
    check_universal_rules_presence(bundled_dir, issues)
    check_no_universal_rules_in_templates(prompts, issues)

    # Report.
    return print_report(total, system_count, issues, args.strict)


if __name__ == "__main__":
    sys.exit(main())
