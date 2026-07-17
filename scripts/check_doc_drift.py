#!/usr/bin/env python3
"""
Narrare Documentation Drift Checker.

Validates that documented version numbers, ADR cross-references,
spec/RULE-XX alignment, and checker terminology match reality.

Check families:
  - Node.js version consistency (via doc_drift.tool_version_checks)
  - pnpm version consistency (via doc_drift.tool_version_checks)
  - ADR cross-reference and status consistency
  - Spec/RULE-XX reference alignment
  - Checker terminology alignment
  - Lookup-context drift (pydantic-ai/mem0/coverage/phantom commands — review-04 AUFG-04-13)
  - Just-recipe doc-drift (phantom `just <recipe>` references — review-04 AUFG-04-02/04)
  - Agent-name doc-drift (fake subagent_type references — review-04 AUFG-04-15)
  - Removed-governance-artifact references (WARNING-ONLY ratcheted baseline)
  - §7 stub-variable detector (WARNING-ONLY ratcheted baseline)

Exit codes:
  0: No drift detected — all checks passed.
  1: Drift found — at least one critical finding.

Usage:
  python scripts/check_doc_drift.py                                # human-readable
  python scripts/check_doc_drift.py --json                         # JSON for CI
  python scripts/check_doc_drift.py --verbose                      # detailed steps
  python scripts/check_doc_drift.py --governance-only              # skip tool checks
  python scripts/check_doc_drift.py --governance-only --checks stub_variable

See: docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06)
     docs/architecture/decisions/ADR-041 (Phase 2)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# Allow importing from scripts/ sub-packages.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from doc_drift.adr_checks import DocDriftFinding, check_adr_consistency
from doc_drift.agent_name_checks import check_agent_name_drift
from doc_drift.just_command_checks import check_just_command_drift
from doc_drift.lookup_drift_checks import check_lookup_drift
from doc_drift.removed_governance_refs_checks import check_removed_governance_refs
from doc_drift.spec_checks import check_spec_references
from doc_drift.ssot_locale_path_checks import check_ssot_locale_path
from doc_drift.stub_variable_checks import check_stub_variables
from doc_drift.terminology_checks import check_terminology_alignment
from doc_drift.tool_version_checks import CheckResult, register_tool_checks

# ── Data structures ────────────────────────────────────────────


@dataclass
class DriftReport:
    """Aggregated report of all drift checks."""

    checks: list[CheckResult] = field(default_factory=list[CheckResult])

    @property
    def passed(self) -> bool:
        """True if every individual check passed."""
        return all(c.passed for c in self.checks)

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def failures(self) -> int:
        return sum(1 for c in self.checks if not c.passed)


# ── Governance checks ──────────────────────────────────────────

# Single source of truth for the governance-check inventory. Each entry is
# (check name, check function); ``--checks`` filters this set so a single
# check (e.g. the §7 stub-variable detector) can run in isolation. The
# pre-commit ``stub-variables`` hook uses this to catch a source-file stub
# regression at commit time without running every governance check.
_GOVERNANCE_CHECKS: list[tuple[str, Callable[[], list[DocDriftFinding]]]] = [
    ("adr", check_adr_consistency),
    ("spec", check_spec_references),
    ("terminology", check_terminology_alignment),
    ("lookup", check_lookup_drift),
    ("ssot_locale", check_ssot_locale_path),
    ("just_command", check_just_command_drift),
    ("agent_name", check_agent_name_drift),
    ("removed_governance_refs", check_removed_governance_refs),
    ("stub_variable", check_stub_variables),
]


def _run_governance_checks(
    only: set[str] | None = None,
) -> list[DocDriftFinding]:
    """Run all (or a filtered subset of) doc-drift governance checks.

    Args:
        only: Optional set of check names from :data:`_GOVERNANCE_CHECKS` to
            run; ``None`` runs the full suite.
    """
    findings: list[DocDriftFinding] = []
    for name, check_fn in _GOVERNANCE_CHECKS:
        if only is not None and name not in only:
            continue
        findings.extend(check_fn())
    return findings


# ── Output formatting ──────────────────────────────────────────


def _format_human_check(check: CheckResult, verbose: bool = False) -> str:
    """Format a single check result as a human-readable line."""
    if verbose:
        detail = f"  Detail: {check.detail}"
        pat = f"  Pattern: /{check.pattern}/"
        icon = "✅" if check.passed else "❌"
        return f"  {icon} {check.file}\n{pat}\n{detail}"
    icon = "✅" if check.passed else "❌"
    return f"{icon} {check.file}: {check.detail}"


def print_human_report(report: DriftReport, verbose: bool = False) -> None:
    """Print a human-readable drift report to stdout."""
    if verbose:
        print("=" * 60)
        print("  NARRARE DOCUMENTATION DRIFT CHECKER")
        print("=" * 60)
        print()

    for check in report.checks:
        print(_format_human_check(check, verbose=verbose))

    print()
    if report.passed:
        print(f"✅ All {report.total} checks passed — no drift detected.")
    else:
        print(f"❌ {report.failures}/{report.total} checks failed — drift detected!")
        if not verbose:
            print()
            print("Failed checks:")
            for check in report.checks:
                if not check.passed:
                    print(f"  • {check.file}")
                    print(f"    Expected pattern: /{check.pattern}/")
                    print(f"    Detail: {check.detail}")


def print_json_report(report: DriftReport) -> None:
    """Print a JSON-formatted report for CI pipeline consumption."""
    output = {
        "passed": report.passed,
        "total": report.total,
        "failures": report.failures,
        "checks": [
            {
                "file": c.file,
                "pattern": c.pattern,
                "passed": c.passed,
                "detail": c.detail,
            }
            for c in report.checks
        ],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


# ── CLI entry point ────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Narrare Documentation Drift Checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/check_doc_drift.py\n"
            "  python scripts/check_doc_drift.py --json\n"
            "  python scripts/check_doc_drift.py --verbose\n"
            "  python scripts/check_doc_drift.py --governance-only\n"
            "  python scripts/check_doc_drift.py --governance-only --checks stub_variable\n"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (for CI consumption)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed per-check information",
    )
    parser.add_argument(
        "--governance-only",
        action="store_true",
        help="Run only governance checks (ADR/spec/terminology), skip tool version checks",
    )
    parser.add_argument(
        "--checks",
        nargs="+",
        choices=[name for name, _ in _GOVERNANCE_CHECKS],
        default=None,
        help=(
            "Run only the named governance check(s) "
            f"(choices: {', '.join(name for name, _ in _GOVERNANCE_CHECKS)}). "
            "Default: all governance checks. Combine with --governance-only "
            "to also skip tool version checks (used by the pre-commit "
            "stub-variables hook to run the §7 detector on source changes)."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run all drift checks. Returns 0 if clean, 1 if drift found."""
    args = parse_args(argv)
    has_critical = False

    # ── Phase 1: Tool version checks (Node.js + pnpm) ────────
    if not args.governance_only:
        tool_checks = register_tool_checks()
        report = DriftReport()
        for _name, check_fn in tool_checks:
            results = check_fn()
            report.checks.extend(results)

        if args.json:
            print_json_report(report)
        else:
            print_human_report(report, verbose=args.verbose)

        if not report.passed:
            has_critical = True

    # ── Phase 2: Governance checks ───────────────────────────
    only = set(args.checks) if args.checks else None
    findings = _run_governance_checks(only=only)
    critical = [f for f in findings if f.severity == "critical"]
    warnings = [f for f in findings if f.severity == "warning"]

    if findings:
        print()
        print("── Governance Checks ──")
        for f in findings:
            label = f"[{f.severity.upper()}]"
            print(f"  {label} {f.file}: {f.message}")

    if critical:
        print(f"\n❌ {len(critical)} critical doc drift findings")
        has_critical = True
    elif warnings:
        print(f"\n⚠️  {len(warnings)} doc drift warnings")

    if not findings and not has_critical:
        print("\n✅ Doc drift check passed")
    elif not has_critical:
        print("\n✅ Doc drift check passed (with warnings)")

    return 1 if has_critical else 0


if __name__ == "__main__":
    sys.exit(main())
