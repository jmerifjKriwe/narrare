#!/usr/bin/env python3
"""Check per-module coverage against ratcheted baselines and RULE-10 minimums.

Reads pytest's coverage XML report and checks each module against
(a) its RULE-10 target (hard floor — blocking) and (b) its ratcheted
baseline (soft ratchet — warning on regression, non-blocking as long
as the target is met).

Usage:
    python scripts/check_module_coverage.py               (warnings for regressions + below-target)
    python scripts/check_module_coverage.py --fail         (strict: below target = exit 1)
    python scripts/check_module_coverage.py --warning-only (all warnings, never fails)
    python scripts/check_module_coverage.py --update-baselines
    python scripts/check_module_coverage.py --json         (machine-readable)

Exit codes:
    0: All modules at or above RULE-10 targets (or --warning-only)
    1: At least one module below its RULE-10 target (--fail mode only)
    2: Coverage XML not found or invalid

See: docs/_shared/CONSTRAINTS.md (RULE-10)
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET  # nosec B405  # CI-generated coverage XML is trusted
from pathlib import Path

from _coverage_model import (  # type: ignore[import-untyped]
    BASELINES_FILE,
    DEFAULT_COVERAGE_XML,
    STATUS_BELOW_TARGET,
    STATUS_REGRESSION,
    CoverageReport,
    parse_coverage_xml,
    save_baselines,
)

# ── Output formatting ──────────────────────────────────────────


def _format_text_report(report: CoverageReport) -> str:
    """Format *report* as a human-readable table."""
    lines: list[str] = [
        "",
        "MODULE COVERAGE REPORT (RULE-10 + ratchet baselines)",
        "=" * 96,
        "",
    ]

    header = (
        f"{'Package':<42} {'Source':>6} {'Coverage':>8} {'Baseline':>9} {'Target':>7} {'Status':>8}"
    )
    lines.append(header)
    lines.append("-" * 96)

    for mod in report.modules:
        lines.append(
            f"{mod.display_path:<42} {mod.source:>6} {mod.coverage_pct:>7.1f}% "
            f"{mod.baseline:>8.1f}% {mod.target:>6}% {mod.status:>8}"
        )

    lines.append("-" * 96)
    lines.append(
        f"Summary: {report.total} modules — "
        f"{report.passing} meet target, "
        f"{report.warned} regressed (above target), "
        f"{report.failed} below target"
    )
    lines.append("")

    return "\n".join(lines)


def _format_json_report(report: CoverageReport) -> str:
    """Format *report* as JSON for machine consumption."""
    data = {
        "modules": [
            {
                "package": m.package,
                "display_path": m.display_path,
                "source": m.source,
                "coverage_pct": m.coverage_pct,
                "baseline": m.baseline,
                "target": m.target,
                "status": m.status,
            }
            for m in report.modules
        ],
        "summary": {
            "total": report.total,
            "passing": report.passing,
            "warned": report.warned,
            "failed": report.failed,
        },
    }
    return json.dumps(data, indent=2)


# ── CLI ────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Check per-module coverage against ratcheted baselines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  All modules at or above RULE-10 targets (or --warning-only)\n"
            "  1  At least one module below its RULE-10 target (--fail only)\n"
            "  2  Coverage XML not found or invalid\n"
            "\n"
            "RULE-10 targets (aspirational — warnings until met):\n"
            "  core/llm/, core/prompts/     95%\n"
            "  core/* (other)               90%\n"
            "  apps/api/*                   80%\n"
            "\n"
            "Use --update-baselines after intentionally raising coverage.\n"
        ),
    )
    parser.add_argument(
        "--coverage-xml",
        type=Path,
        default=DEFAULT_COVERAGE_XML,
        help=f"Path to coverage XML report (default: {DEFAULT_COVERAGE_XML.name})",
    )
    parser.add_argument(
        "--warning-only",
        action="store_true",
        help="Print warnings but do not fail CI (default behaviour)",
    )
    parser.add_argument(
        "--fail",
        action="store_true",
        help="Exit 1 if any module is below its RULE-10 target (hard floor)",
    )
    parser.add_argument(
        "--update-baselines",
        action="store_true",
        help="Capture current coverage as new baselines and exit",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output results as JSON for machine consumption",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run per-module coverage checks and return exit code."""
    args = parse_args(argv)

    # --warning-only overrides --fail when both are given.
    strict: bool = args.fail and not args.warning_only

    # ── Validate coverage XML ──────────────────────────────
    if not args.coverage_xml.exists():
        print(
            f"Error: {args.coverage_xml} not found. Run pytest with --cov-report=xml first.",
            file=sys.stderr,
        )
        return 2

    # ── Parse coverage XML (no baselines first, for --update-baselines) ──
    try:
        raw_report = parse_coverage_xml(args.coverage_xml, baselines={})
    except ET.ParseError as exc:
        print(f"Error: Failed to parse {args.coverage_xml}: {exc}", file=sys.stderr)
        return 2

    if not raw_report.modules:
        print("No packages found in coverage XML.", file=sys.stderr)
        return 0

    # ── Update baselines mode ──────────────────────────────
    if args.update_baselines:
        packages = {m.package: m.coverage_pct for m in raw_report.modules}
        save_baselines(packages)
        print(f"Updated {len(packages)} package baselines in {BASELINES_FILE}")
        return 0

    # ── Load baselines and re-parse with them ──────────────
    from _coverage_model import load_baselines  # type: ignore[import-untyped]

    baselines = load_baselines()
    try:
        report = parse_coverage_xml(args.coverage_xml, baselines=baselines)
    except ET.ParseError as exc:
        print(f"Error: Failed to parse {args.coverage_xml}: {exc}", file=sys.stderr)
        return 2

    # ── Output ─────────────────────────────────────────────
    if args.json_output:
        print(_format_json_report(report))
    else:
        print(_format_text_report(report))

    # ── GitHub Actions annotations ─────────────────────────
    for mod in report.modules:
        if mod.status == STATUS_BELOW_TARGET:
            annotation = "::error::" if strict else "::warning::"
            print(
                f"{annotation}BELOW_TARGET: {mod.display_path} coverage "
                f"{mod.coverage_pct:.1f}% is below {mod.target}% target "
                f"(baseline: {mod.baseline:.1f}%)"
            )
        elif mod.status == STATUS_REGRESSION:
            print(
                f"::warning::REGRESSION: {mod.display_path} coverage "
                f"{mod.coverage_pct:.1f}% dropped below baseline {mod.baseline:.1f}% "
                f"(still above {mod.target}% target)"
            )

    # ── Exit code ──────────────────────────────────────────
    if strict and report.failed > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
