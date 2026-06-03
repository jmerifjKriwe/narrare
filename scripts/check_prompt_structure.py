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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.prompt_check_types import Issue

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

# ── Constants ──────────────────────────────────────────────────

BUNDLED_DIR = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
PROMPT_WARNING_BASELINE_SECTION = "prompt_structure_warnings"


def _ensure_import_paths() -> None:
    """Make script-local helpers and project-root packages importable."""
    for path in (SCRIPTS_DIR, ROOT):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)


def collect_issues(bundled_dir: Path) -> tuple[int, int, list[Issue]]:
    """Collect prompt structure issues without printing a report."""
    _ensure_import_paths()
    from prompt_checks import (
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

    prompts = discover_prompts(bundled_dir)
    system_prompts = [p for p in prompts if p.is_system_md]

    issues: list[Issue] = []
    for pf in prompts:
        check_frontmatter(pf, issues)
        check_required_sections(pf, issues)
        check_security(pf, issues)
        check_file_size(pf, issues)

    check_variable_consistency(prompts, issues)
    check_locale_coverage(prompts, issues)
    check_meta_guardrails(prompts, issues)
    check_universal_rules_presence(bundled_dir, issues)
    check_no_universal_rules_in_templates(prompts, issues)

    return len(prompts), len(system_prompts), issues


def warning_fingerprints(issues: list[Issue]) -> set[str]:
    """Return stable fingerprints for WARN-level prompt findings."""
    _ensure_import_paths()
    from scripts.architecture.baselines import stable_fingerprint

    return {
        stable_fingerprint(issue.file_path, issue.message)
        for issue in issues
        if issue.level == "WARN"
    }


# ── Reporting ──────────────────────────────────────────────────


def print_report(
    total: int,
    system_count: int,
    issues: list[Issue],
    strict: bool,
    baseline_path: Path | None = None,
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

    if baseline_path is not None:
        _ensure_import_paths()
        from scripts.architecture.baselines import (
            compare_section,
            format_comparison,
        )

        comparison = compare_section(
            warning_fingerprints(issues),
            PROMPT_WARNING_BASELINE_SECTION,
            baseline_path,
        )
        print(format_comparison(comparison, "Prompt warning ratchet"))
        if not comparison.ok:
            print("RESULT: New prompt WARN(s) exceed baseline")
            return 1

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
    _ensure_import_paths()
    from scripts.architecture.baselines import DEFAULT_BASELINE_PATH

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
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="JSON baseline used to fail only new WARN debt (default: ai-gate-baseline.json).",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Disable prompt WARN ratchet comparison.",
    )
    args = parser.parse_args()

    bundled_dir = args.path
    if not bundled_dir.is_dir():
        print(
            f"ERROR: Prompt directory not found: {bundled_dir}",
            file=sys.stderr,
        )
        return 1

    total, system_count, issues = collect_issues(bundled_dir)

    if total == 0:
        print("WARN: No .md files found in bundled prompts directory.")
        return 0

    # Report.
    baseline_path = None if args.no_baseline else args.baseline
    return print_report(total, system_count, issues, args.strict, baseline_path)


if __name__ == "__main__":
    sys.exit(main())
