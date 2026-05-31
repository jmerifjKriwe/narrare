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

import yaml
from adoption.scorer import (
    PASS_THRESHOLD,
    AdoptionReport,
    compute_adoption_report,
)
from prompt_checks_crossfile import discover_prompts

# ── Constants ──────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "scripts" / "architecture" / "adoption-registry.yaml"
BUNDLED_DIR = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"


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

        parts: list[str] = []
        if cat.missing_must:
            parts.append(f"missing MUST: {', '.join(cat.missing_must)}")
        if cat.missing_should:
            parts.append(f"missing SHOULD: {', '.join(cat.missing_should)}")
        if cat.missing_locales:
            locale_strs = [f"{k}: missing {', '.join(v)}" for k, v in cat.missing_locales.items()]
            parts.append(f"i18n gaps: {'; '.join(locale_strs)}")

        detail_str = f"  ({'; '.join(parts)})" if parts else ""
        lines.append(f"  {cat.category:<14} {cat.score:.2f} {icon}{fallback_info}{detail_str}")

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
        "categories": [
            {
                "category": cat.category,
                "score": round(cat.score, 4),
                "status": cat.status,
                "missing_must": cat.missing_must,
                "missing_should": cat.missing_should,
                "missing_locales": cat.missing_locales,
                "inline_fallbacks": cat.inline_fallbacks,
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

    return _exit_code(report.status)


if __name__ == "__main__":
    sys.exit(main())
