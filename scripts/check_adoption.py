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
import json
import sys
from pathlib import Path
from typing import Any, cast

# Allow importing from the same directory (scripts/).
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from adoption.audit_report import build_audit_report
from adoption.scorer import (
    PASS_THRESHOLD,
    AdoptionReport,
    compute_adoption_report,
)
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


# ── Output formatting ──────────────────────────────────────────────

_STATUS_ICON = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}  # nosec B105


def _format_human(report: AdoptionReport) -> str:
    """Format the adoption report as a human-readable string."""
    lines: list[str] = []
    lines.append(f"\nFeature Adoption Score: {report.overall_score:.2f} ({report.status})\n")

    # Per-category breakdown.
    for cat in report.categories:
        icon = _STATUS_ICON.get(cat.status, "  ")
        fallback_info = (
            f" ({cat.inline_fallbacks} inline fallback(s))" if cat.inline_fallbacks else ""
        )

        # Mode summary.
        if cat.modes:
            mode_count = len(cat.modes)
            rt_count = sum(1 for m in cat.modes if m.runtime_verified)
            ad_count = sum(1 for m in cat.modes if m.adopted)
            mode_marker = f"  [{mode_count} modes, {rt_count} runtime_verified, {ad_count} adopted]"
        else:
            mode_marker = ""

        parts: list[str] = []
        if cat.missing_must:
            parts.append(f"missing MUST: {', '.join(cat.missing_must)}")
        if cat.missing_should:
            parts.append(f"missing SHOULD: {', '.join(cat.missing_should)}")
        if cat.missing_locales:
            locale_strs = [f"{k}: missing {', '.join(v)}" for k, v in cat.missing_locales.items()]
            parts.append(f"i18n gaps: {'; '.join(locale_strs)}")

        detail_str = f"  ({'; '.join(parts)})" if parts else ""
        lines.append(
            f"  {cat.category:<14} {cat.score:.2f} {icon}{mode_marker}{fallback_info}{detail_str}"
        )

        # Mode-level breakdown.
        for mode in cat.modes:
            micon = _STATUS_ICON.get(mode.status, "  ")
            rt_icon = "✅" if mode.runtime_verified else "❌"
            ad_icon = "✅" if mode.adopted else "❌"

            rt_hint = ""
            if not mode.runtime_verified:
                failed = [rd for rd in mode.runtime_details if rd.evidence_status != "verified"]
                if failed:
                    rt_hint = f" {failed[0].requirement}={failed[0].declared}"

            lines.append(
                f"    {mode.mode:<24} {mode.score:.2f} {micon} "
                f"static {'✅' if mode.static_verified else '❌'} | "
                f"runtime {rt_icon}{rt_hint} | adopted {ad_icon}"
            )

            # Runtime failure details.
            if not mode.runtime_verified:
                for rd in mode.runtime_details:
                    if rd.evidence_status != "verified":
                        lines.append(f"      → runtime: {rd.requirement} declared '{rd.declared}'")

    lines.append("")
    overall_icon = _STATUS_ICON.get(report.status, "")
    lines.append(
        f"Overall: {report.status} {overall_icon} "
        f"(threshold: {PASS_THRESHOLD}, actual: {report.overall_score:.2f})"
    )
    lines.append("See: scripts/architecture/adoption-registry.yaml")
    lines.append("")
    return "\n".join(lines)


def _format_json(report: AdoptionReport) -> str:
    """Format the adoption report as JSON."""
    data = {
        "overall_score": round(report.overall_score, 4),
        "status": report.status,
        "total_inline_fallbacks": report.total_inline_fallbacks,
        "mode_count": report.mode_count,
        "runtime_verified_count": report.runtime_verified_count,
        "adopted_count": report.adopted_count,
        "categories": [
            {
                "category": cat.category,
                "score": round(cat.score, 4),
                "status": cat.status,
                "missing_must": cat.missing_must,
                "missing_should": cat.missing_should,
                "missing_locales": cat.missing_locales,
                "inline_fallbacks": cat.inline_fallbacks,
                "modes": [
                    {
                        "mode": m.mode,
                        "score": round(m.score, 4),
                        "status": m.status,
                        "static_verified": m.static_verified,
                        "runtime_verified": m.runtime_verified,
                        "adopted": m.adopted,
                        "runtime_details": [
                            {
                                "requirement": rd.requirement,
                                "declared": rd.declared,
                                "evidence_status": rd.evidence_status,
                                "note": rd.note,
                            }
                            for rd in m.runtime_details
                        ],
                    }
                    for m in cat.modes
                ],
            }
            for cat in report.categories
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


# ── Exit code ──────────────────────────────────────────────────────


def _exit_code(status: str) -> int:
    if status == "PASS":
        return 0
    if status == "WARN":
        return 2
    return 1


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
    args = parser.parse_args()

    registry = load_registry(args.registry)

    if not args.prompts.is_dir():
        print(
            f"ERROR: Prompt directory not found: {args.prompts}",
            file=sys.stderr,
        )
        return 1

    prompts = discover_prompts(args.prompts)

    report = compute_adoption_report(registry, prompts)

    if args.json:
        print(_format_json(report))
    else:
        print(_format_human(report))

    if not args.no_baseline:
        comparison = compare_section(
            adoption_debt_fingerprints(report),
            ADOPTION_BASELINE_SECTION,
            args.baseline,
        )
        print(format_comparison(comparison, "Adoption debt ratchet"))
        if not comparison.ok:
            return 1

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

    return _exit_code(report.status)


if __name__ == "__main__":
    sys.exit(main())
