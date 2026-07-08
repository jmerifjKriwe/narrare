#!/usr/bin/env python3
"""CLI orchestration for adoption scoring — extracted from check_adoption.py.

Handles argument parsing, command orchestration, and exit code computation.
Domain logic (loading registry, computing fingerprints) lives in
``check_adoption.py`` and is accessed through the module reference
``_ca`` to preserve monkeypatch compatibility for tests.

Exit codes:
    0: Score >= 0.85 (PASS)
    2: Score 0.70-0.85 (WARN)
    1: Score < 0.70 (FAIL)

Usage:
    python scripts/check_adoption.py
    python scripts/check_adoption.py --json
    python scripts/check_adoption.py --help

See:
    - docs/architecture/decisions/ADR-025-feature-adoption-infrastructure.md
    - scripts/check_adoption.py (thin entry point)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from prompt_checks_crossfile import discover_prompts
from scripts.architecture.baselines import (
    DEFAULT_BASELINE_PATH,
    compare_section,
    format_comparison,
)

from adoption.audit_report import build_audit_report
from adoption.prompt_path_adoption import check_prompt_path_adoption
from adoption.report_format import exit_code as _exit_code
from adoption.report_format import format_human as _format_human
from adoption.report_format import format_json as _format_json
from adoption.scorer import compute_adoption_report
from adoption.script_evidence_repo import ScriptEvidenceRepository


def main() -> int:
    """Parse arguments, orchestrate adoption scoring, and return exit code."""
    # Lazy import: accessed through the check_adoption module reference so
    # that monkeypatch.setattr(check_adoption, "load_registry", fake) works
    # in tests — main() resolves these names dynamically via the module ref.
    # The import is safe from circular deps because check_adoption is fully
    # loaded by the time main() is called (it's already imported from cli).
    from scripts import check_adoption as _ca

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
        default=_ca.REGISTRY_PATH,
        help="Path to adoption-registry.yaml (default: auto-detected).",
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        default=_ca.BUNDLED_DIR,
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

    registry = _ca.load_registry(args.registry)

    if not args.prompts.is_dir():
        print(
            f"ERROR: Prompt directory not found: {args.prompts}",
            file=sys.stderr,
        )
        return 1

    prompts = discover_prompts(args.prompts)
    evidence_repo = (
        ScriptEvidenceRepository(_ca.DEFAULT_EVIDENCE_REPO_FILE) if args.evidence_repo else None
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

    # ADR-048 — Mode 2 declaration validation + placeholder evidence rejection.
    from adoption.mode2_validation import validate_adoption_mode2

    mode2_report = validate_adoption_mode2(
        registry,
        evidence_dir=args.evidence_dir,
    )

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

        if mode2_report.findings:
            print("\nADR-048 Mode 2 validation + placeholder evidence:")
            for f in mode2_report.findings:
                icon = "❌" if f.severity == "critical" else "⚠️ "
                print(f"  {icon} [{f.code}] {f.message}")
        else:
            print("\n✅ ADR-048 Mode 2 validation: no issues")

    exit_code = _exit_code(report.status)
    # Prompt-path-compliance violations are hard failures (C.2 root cause).
    if pp_critical:
        exit_code = 1
    if not args.no_baseline:
        comparison = compare_section(
            _ca.adoption_debt_fingerprints(report),
            _ca.ADOPTION_BASELINE_SECTION,
            args.baseline,
        )
        print(format_comparison(comparison, "Adoption debt ratchet"))
        if not comparison.ok:
            return 1
        if report.status == "GOVERNED_DEBT":
            exit_code = 0

    if pp_critical and exit_code == 0:
        exit_code = 1

    # ADR-048 — Mode 2 critical findings are hard failures.
    if mode2_report.has_critical and exit_code == 0:
        exit_code = 1

    if args.audit:
        audit = build_audit_report(report, registry, args.baseline)
        if args.json:
            print(audit.to_json())
        else:
            print(audit.to_markdown())

    if args.drift:
        # Registry drift check.
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

        # Doc drift check — pass empty argv so it doesn't re-parse --drift.
        from scripts.check_doc_drift import main as check_doc_drift_main

        doc_result = check_doc_drift_main(argv=[])
        if doc_result != 0:
            print(f"\n⚠️  Doc drift check returned exit code {doc_result}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
