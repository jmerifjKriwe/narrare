#!/usr/bin/env python3
"""Output formatting for adoption reports (RULE-04 extract).

Extracted from ``check_adoption.py`` to keep that file under the 400-line
RULE-04 limit. Contains human-readable and JSON formatting for
``AdoptionReport`` as well as the exit-code helper.

See:
    - ``scripts/check_adoption.py`` (the main CI entry point)
    - ``docs/architecture/decisions/ADR-025-feature-adoption-infrastructure.md``
"""

from __future__ import annotations

import json
from typing import Any

from adoption.scorer import PASS_THRESHOLD, AdoptionReport

STATUS_ICON: dict[str, str] = {
    "PASS": "✅",
    "WARN": "⚠️ ",
    "FAIL": "❌",
    "STATIC_ONLY": "i ",
    "GOVERNED_DEBT": "⚠️ ",
}  # nosec B105


def format_human(report: AdoptionReport) -> str:
    """Format the adoption report as a human-readable string."""
    lines: list[str] = []
    lines.append(f"\nFeature Adoption Score: {report.overall_score:.2f} ({report.status})\n")

    # Per-category breakdown.
    for cat in report.categories:
        icon = STATUS_ICON.get(cat.status, "  ")
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
            micon = STATUS_ICON.get(mode.status, "  ")
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
    overall_icon = STATUS_ICON.get(report.status, "")
    lines.append(
        f"Overall: {report.status} {overall_icon} "
        f"(threshold: {PASS_THRESHOLD}, actual: {report.overall_score:.2f})"
    )
    lines.append("See: scripts/architecture/adoption-registry.yaml")
    lines.append("")
    return "\n".join(lines)


def format_json(
    report: AdoptionReport,
    pp_findings: list[Any] | None = None,
) -> str:
    """Format the adoption report as JSON."""
    data = {
        "overall_score": round(report.overall_score, 4),
        "status": report.status,
        "total_inline_fallbacks": report.total_inline_fallbacks,
        "mode_count": report.mode_count,
        "runtime_verified_count": report.runtime_verified_count,
        "adopted_count": report.adopted_count,
        "prompt_path_compliance": {
            "violations": len(pp_findings or []),
            "findings": [
                {
                    "mode_key": f.mode_key,
                    "severity": f.severity,
                    "message": f.message,
                }
                for f in (pp_findings or [])
            ],
        },
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


def exit_code(status: str) -> int:
    """Compute exit code from status string."""
    if status in {"PASS", "STATIC_ONLY"}:
        return 0
    if status in {"WARN", "GOVERNED_DEBT"}:
        return 2
    return 1
