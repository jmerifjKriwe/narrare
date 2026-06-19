#!/usr/bin/env python3
"""
Narrare Feature Adoption Score — CI script.

Computes per-category and overall adoption scores based on the
adoption registry and bundled prompt files.

Exit codes:
    0: Score >= 0.85 (PASS)
    2: Score 0.70-0.85 (WARN)
    1: Score < 0.70 (FAIL)

Usage:
    python scripts/check_adoption.py
    python scripts/check_adoption.py --json
    python scripts/check_adoption.py --help

See: docs/architecture/decisions/025-feature-adoption-infrastructure.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, cast

# Allow importing from the same directory (scripts/).
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from adoption.audit_report import build_audit_report
from adoption.prompt_path_adoption import check_prompt_path_adoption
from adoption.report_format import (
    exit_code as _exit_code,
)
from adoption.report_format import (
    format_human as _format_human,
)
from adoption.report_format import (
    format_json as _format_json,
)
from adoption.scorer import (
    AdoptionReport,
    compute_adoption_report,
)
from adoption.script_evidence_repo import ScriptEvidenceRepository
from prompt_checks_crossfile import discover_prompts
from scripts.architecture.baselines import (
    DEFAULT_BASELINE_PATH,
    compare_section,
    format_comparison,
    stable_fingerprint,
)

# ── Constants ──────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "scripts" / "architecture" / "adoption-registry.yaml"
BUNDLED_DIR = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"
ADOPTION_BASELINE_SECTION = "adoption_debt"
DEFAULT_EVIDENCE_REPO_FILE = ROOT / ".evidence" / "invocations.jsonl"


def adoption_debt_fingerprints(report: AdoptionReport) -> set[str]:
    """Return stable fingerprints for non-failing adoption debt."""
    items: set[str] = set()
    for category in report.categories:
        if category.status == "WARN":
            items.add(stable_fingerprint(category.category, "status", category.status))
        for missing in category.missing_must:
            items.add(stable_fingerprint(category.category, "missing_must", missing))
        for missing in category.missing_should:
            items.add(stable_fingerprint(category.category, "missing_should", missing))
        for prompt_key, locales in category.missing_locales.items():
            for locale in locales:
                items.add(
                    stable_fingerprint(category.category, "missing_locale", prompt_key, locale)
                )
        if category.inline_fallbacks:
            items.add(
                stable_fingerprint(
                    category.category,
                    "inline_fallback_count",
                    category.inline_fallbacks,
                )
            )
        # Mode-level fingerprints for runtime gaps.
        for mode in category.modes:
            if mode.static_verified and not mode.runtime_verified:
                for rd in mode.runtime_details:
                    if rd.evidence_status != "verified":
                        items.add(
                            stable_fingerprint(
                                category.category,
                                mode.mode,
                                "runtime",
                                rd.requirement,
                                rd.evidence_status,
                            )
                        )
            if mode.static_verified and not mode.adopted:
                items.add(stable_fingerprint(category.category, mode.mode, "not_adopted"))
    return items


# ── Registry loading ───────────────────────────────────────────────


def load_registry(path: Path) -> dict[str, Any]:
    """Load the adoption registry YAML."""
    if not path.exists():
        print(f"ERROR: Adoption registry not found: {path}", file=sys.stderr)
        sys.exit(1)
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not data or not isinstance(data, dict):
        print("ERROR: Adoption registry is not a valid YAML mapping", file=sys.stderr)
        sys.exit(1)
    return cast("dict[str, Any]", data)


# ── Output formatting (extracted to adoption/report_format.py) ──────


# ── Main ───────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute Narrare feature adoption scores.",
        epilog=("Exit codes: 0 = PASS (>= 0.85), 2 = WARN (0.70-0.85), 1 = FAIL (< 0.70)"),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=REGISTRY_PATH,
        help="Path to adoption-registry.yaml (default: auto-detected).",
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        default=BUNDLED_DIR,
        help="Path to _bundled/ directory (default: auto-detected).",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="JSON baseline used to fail new adoption debt only.",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Disable adoption debt ratchet comparison.",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Also generate and print an AuditReport (ADR-040 Decision 3).",
    )
    parser.add_argument(
        "--drift",
        action="store_true",
        help="Also run registry drift + doc drift checks (P3 Layer 5).",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=None,
        help="Path to .evidence/ directory with probe evidence (default: none).",
    )
    parser.add_argument(
        "--evidence-repo",
        action="store_true",
        default=False,
        help="Use EvidenceRepository for probe evidence (production mode).",
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        default=False,
        help=(
            "Explicitly run without runtime evidence and label runtime-required modes STATIC_ONLY."
        ),
    )
    args = parser.parse_args()

    if args.static_only and args.evidence_dir is not None:
        print("ERROR: --static-only cannot be combined with --evidence-dir.", file=sys.stderr)
        return 1
    if args.static_only and args.evidence_repo:
        print("ERROR: --static-only cannot be combined with --evidence-repo.", file=sys.stderr)
        return 1
    if args.evidence_dir is not None and args.evidence_repo:
        print("ERROR: --evidence-dir cannot be combined with --evidence-repo.", file=sys.stderr)
        return 1

    registry = load_registry(args.registry)

    if not args.prompts.is_dir():
        print(
            f"ERROR: Prompt directory not found: {args.prompts}",
            file=sys.stderr,
        )
        return 1

    prompts = discover_prompts(args.prompts)
    evidence_repo = (
        ScriptEvidenceRepository(DEFAULT_EVIDENCE_REPO_FILE) if args.evidence_repo else None
    )

    report = compute_adoption_report(
        registry,
        prompts,
        evidence_dir=str(args.evidence_dir) if args.evidence_dir else None,
        evidence_repo=evidence_repo,
    )

    # ADR-046 D.5 — prompt-path compliance per-intent metric (RULE-02b).
    pp_findings = check_prompt_path_adoption(registry)
    pp_critical = [f for f in pp_findings if f.severity == "critical"]

    if args.json:
        print(_format_json(report, pp_findings))
    else:
        print(_format_human(report))
        if pp_findings:
            print("\nADR-046 prompt-path compliance (RULE-02b):")
            for f in pp_findings:
                icon = "❌" if f.severity == "critical" else "⚠️ "
                print(f"  {icon} {f.mode_key}: {f.message}")
        else:
            print("\n✅ ADR-046 prompt-path compliance: all intents compliant")

    exit_code = _exit_code(report.status)
    # Prompt-path-compliance violations are hard failures (C.2 root cause).
    if pp_critical:
        exit_code = 1
    if not args.no_baseline:
        comparison = compare_section(
            adoption_debt_fingerprints(report),
            ADOPTION_BASELINE_SECTION,
            args.baseline,
        )
        print(format_comparison(comparison, "Adoption debt ratchet"))
        if not comparison.ok:
            return 1
        if report.status == "GOVERNED_DEBT":
            exit_code = 0

    if pp_critical and exit_code == 0:
        exit_code = 1

    if args.audit:
        audit = build_audit_report(report, registry, args.baseline)
        if args.json:
            print(audit.to_json())
        else:
            print(audit.to_markdown())

    if args.drift:
        # Registry drift check
        from scripts.check_registry_drift import DriftReport, check_registry_drift

        registry_findings = check_registry_drift()
        registry_report = DriftReport(findings=registry_findings)
        if registry_report.has_critical:
            critical = [f for f in registry_findings if f.severity == "critical"]
            print(f"\n❌ Registry drift: {len(critical)} critical findings")
            for f in critical:
                print(f"  [{f.category}/{f.mode}] {f.message}")
        else:
            print("\n✅ Registry drift: no critical findings")

        # Doc drift check — pass empty argv so it doesn't re-parse --drift
        from scripts.check_doc_drift import main as check_doc_drift_main

        doc_result = check_doc_drift_main(argv=[])
        if doc_result != 0:
            print(f"\n⚠️  Doc drift check returned exit code {doc_result}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
