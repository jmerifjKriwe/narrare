#!/usr/bin/env python3
"""
Narrare Documentation Drift Checker.

Validates that documented version numbers, ADR cross-references,
spec/RULE-XX alignment, and checker terminology match reality.

Check families:
  - Node.js version consistency (Phase 1)
  - ADR cross-reference and status consistency (Phase 2)
  - Spec/RULE-XX reference alignment (Phase 2)
  - Checker terminology alignment (Phase 2)

Exit codes:
  0: No drift detected — all checks passed.
  1: Drift found — at least one critical finding.

Usage:
  python scripts/check_doc_drift.py                        # human-readable
  python scripts/check_doc_drift.py --json                 # JSON for CI
  python scripts/check_doc_drift.py --verbose              # detailed steps
  python scripts/check_doc_drift.py --governance-only      # skip Node checks

See: docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06)
     docs/architecture/decisions/ADR-041 (Phase 2)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
from pathlib import Path

# Allow importing from scripts/ sub-packages.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from doc_drift.adr_checks import DocDriftFinding, check_adr_consistency
from doc_drift.spec_checks import check_spec_references
from doc_drift.terminology_checks import check_terminology_alignment

# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_NODE_VERSION = "24"


# ── Data structures ────────────────────────────────────────────


@dataclass
class CheckResult:
    """Result of a single drift check against one file/pattern pair."""

    file: str
    pattern: str
    passed: bool
    detail: str = ""


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


# ── Check helpers ──────────────────────────────────────────────


def _read_file(path: str) -> str | None:
    """Read a file relative to REPO_ROOT."""
    full_path = REPO_ROOT / path
    if not full_path.exists():
        return None
    try:
        return full_path.read_text(encoding="utf-8")
    except Exception:
        return None


def node_check(
    path: str,
    pattern: str,
    *,
    min_count: int = 1,
    label: str | None = None,
) -> CheckResult:
    """Check a file for a Node-version-related pattern."""
    display_name = label or path
    full_path = REPO_ROOT / path

    if not full_path.exists():
        return CheckResult(
            file=display_name,
            pattern=pattern,
            passed=True,
            detail="⚠  File not found — skipped",
        )

    content = _read_file(path)
    if content is None:
        return CheckResult(
            file=display_name,
            pattern=pattern,
            passed=False,
            detail=f"Error reading {path}",
        )

    matches = re.findall(pattern, content)
    match_count = len(matches)

    if match_count >= min_count:
        return CheckResult(
            file=display_name,
            pattern=pattern,
            passed=True,
            detail=f"Found {match_count} match(es) matching /{pattern}/",
        )

    return CheckResult(
        file=display_name,
        pattern=pattern,
        passed=False,
        detail=(f"Expected ≥{min_count} match(es) of /{pattern}/ but found {match_count}"),
    )


# ── Node check registry ────────────────────────────────────────

CHECKS: list[tuple[str, Callable[[], list[CheckResult]]]] = []


def register_checks() -> None:
    """Register Node.js version drift checks."""
    v = EXPECTED_NODE_VERSION

    CHECKS.append(
        (
            "README.md Node version",
            lambda v=v: [
                node_check(
                    "README.md",
                    rf"Node\.js\s+(?:{v}\+|≥\s*{v})",
                    label="README.md",
                ),
            ],
        )
    )
    CHECKS.append(
        (
            "Deployment guide Node version (x2)",
            lambda v=v: [
                node_check(
                    "docs/development/deployment-guide.md",
                    rf"Node\.js\s+{v}\+",
                    min_count=2,
                    label="docs/development/deployment-guide.md",
                ),
            ],
        )
    )
    CHECKS.append(
        (
            "Context deployment guide Node version",
            lambda v=v: [
                node_check(
                    ".opencode/context/narrare-dev/guides/deployment.md",
                    rf"Node\.js\s+{v}\+",
                    label=".opencode/context/narrare-dev/guides/deployment.md",
                ),
            ],
        )
    )
    CHECKS.append(
        (
            "Evals README Node version",
            lambda v=v: [
                node_check(
                    "evals/README.md",
                    rf"Node\.js\s+≥\s*{v}",
                    label="evals/README.md",
                ),
            ],
        )
    )
    CHECKS.append(
        (
            "CI workflow Node version (x2)",
            lambda v=v: [
                node_check(
                    ".github/workflows/ci.yml",
                    rf'node-version:\s*"{v}"',
                    min_count=2,
                    label=".github/workflows/ci.yml",
                ),
            ],
        )
    )
    CHECKS.append(
        (
            "Eval workflow Node version",
            lambda v=v: [
                node_check(
                    ".github/workflows/eval.yml",
                    rf'node-version:\s*"{v}"',
                    label=".github/workflows/eval.yml",
                ),
            ],
        )
    )
    CHECKS.append(
        (
            "Web package.json engines.node",
            lambda v=v: [
                node_check(
                    "packages/web/package.json",
                    rf'">={v}',
                    label="packages/web/package.json (engines.node)",
                ),
            ],
        )
    )


# ── Governance checks ──────────────────────────────────────────


def _run_governance_checks() -> list[DocDriftFinding]:
    """Run all doc-drift governance checks (Phase 2)."""
    findings: list[DocDriftFinding] = []
    findings.extend(check_adr_consistency())
    findings.extend(check_spec_references())
    findings.extend(check_terminology_alignment())
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
        help="Run only governance checks (ADR/spec/terminology), skip Node checks",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run all drift checks. Returns 0 if clean, 1 if drift found."""
    args = parse_args(argv)
    has_critical = False

    # ── Phase 1: Node.js version checks ──────────────────────
    if not args.governance_only:
        register_checks()
        report = DriftReport()
        for _name, check_fn in CHECKS:
            results = check_fn()
            report.checks.extend(results)

        if args.json:
            print_json_report(report)
        else:
            print_human_report(report, verbose=args.verbose)

        if not report.passed:
            has_critical = True

    # ── Phase 2: Governance checks ───────────────────────────
    findings = _run_governance_checks()
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
