#!/usr/bin/env python3
"""
Check per-module coverage against RULE-10 minimums.

Reads pytest's coverage XML report and checks each module against
its minimum threshold as defined in docs/_shared/CONSTRAINTS.md (RULE-10).

Usage:
    python scripts/check_module_coverage.py
    python scripts/check_module_coverage.py --coverage-xml path/to/coverage.xml
    python scripts/check_module_coverage.py --warning-only   (default)
    python scripts/check_module_coverage.py --fail            (strict mode)
    python scripts/check_module_coverage.py --json            (machine-readable)

Exit codes:
    0: All modules meet thresholds, or warning-only mode
    1: At least one module below threshold (--fail mode only)
    2: Coverage XML not found or invalid

See: docs/_shared/CONSTRAINTS.md (RULE-10)
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET  # nosec B405  # CI-generated coverage XML is trusted
from dataclasses import dataclass, field
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COVERAGE_XML = REPO_ROOT / "coverage.xml"

# RULE-10 module coverage thresholds (from CONSTRAINTS.md).
# Each entry: (dotted package prefix, minimum percentage).
# Matching is longest-prefix-first so more specific rules win.
THRESHOLDS: list[tuple[str, int]] = [
    # Core — highest bar (95% for LLM and prompts)
    ("narrare_core.llm", 95),
    ("narrare_core.prompts", 95),
    # Core — general (90%)
    ("narrare_core", 90),
    # API — general (80%)
    ("narrare", 80),
]

# Global fallback threshold for unmatched packages.
GLOBAL_MINIMUM: int = 60

# Display-path mapping: top-level dotted package → repo-relative path.
_DISPLAY_MAP: dict[str, str] = {
    "narrare_core": "packages/core/narrare_core",
    "narrare": "apps/api/narrare",
}


# ── Data structures ────────────────────────────────────────────


@dataclass
class ModuleCoverage:
    """Coverage result for a single module/package."""

    package: str  # dotted name, e.g. "narrare_core.llm"
    line_rate: float  # 0.0-1.0
    threshold: int  # minimum percentage

    @property
    def coverage_pct(self) -> float:
        """Coverage as a percentage (0.0-100.0)."""
        return round(self.line_rate * 100, 1)

    @property
    def passing(self) -> bool:
        """True when coverage meets or exceeds the threshold."""
        return self.coverage_pct >= self.threshold

    @property
    def display_path(self) -> str:
        """Human-friendly filesystem path for display."""
        parts = self.package.split(".")
        top = parts[0]
        prefix = _DISPLAY_MAP.get(top)
        if prefix:
            if len(parts) == 1:
                return f"{prefix}/"
            return f"{prefix}/{'/'.join(parts[1:])}/"
        return self.package


@dataclass
class CoverageReport:
    """Aggregated coverage report across all modules."""

    modules: list[ModuleCoverage] = field(default_factory=list[ModuleCoverage])

    @property
    def total(self) -> int:
        return len(self.modules)

    @property
    def passed(self) -> int:
        return sum(1 for m in self.modules if m.passing)

    @property
    def failed(self) -> int:
        return self.total - self.passed


# ── Threshold matching ─────────────────────────────────────────


def get_threshold(package_name: str) -> int:
    """Return the minimum coverage threshold for *package_name*.

    Uses longest-prefix matching against :data:`THRESHOLDS`.
    Falls back to :data:`GLOBAL_MINIMUM` for unmatched packages.
    """
    best_len = -1
    best_threshold = GLOBAL_MINIMUM

    for prefix, threshold in THRESHOLDS:
        if (package_name == prefix or package_name.startswith(prefix + ".")) and len(
            prefix
        ) > best_len:
            best_len = len(prefix)
            best_threshold = threshold

    return best_threshold


# ── XML parsing ────────────────────────────────────────────────


def parse_coverage_xml(xml_path: Path) -> CoverageReport:
    """Parse *xml_path* (coverage.xml) and return a :class:`CoverageReport`."""
    tree = ET.parse(xml_path)  # nosec B314  # noqa: S314
    root = tree.getroot()

    report = CoverageReport()

    packages_elem = root.find("packages")
    if packages_elem is None:
        return report

    for pkg in packages_elem.findall("package"):
        name = pkg.attrib.get("name", "")
        line_rate = float(pkg.attrib.get("line-rate", "0"))
        threshold = get_threshold(name)

        report.modules.append(
            ModuleCoverage(
                package=name,
                line_rate=line_rate,
                threshold=threshold,
            )
        )

    # Sort for deterministic output.
    report.modules.sort(key=lambda m: m.package)
    return report


# ── Output formatting ──────────────────────────────────────────


def _format_text_report(report: CoverageReport) -> str:
    """Format *report* as a human-readable table."""
    lines: list[str] = [
        "",
        "MODULE COVERAGE REPORT (RULE-10)",
        "=" * 78,
        "",
    ]

    header = f"{'Package':<50} {'Coverage':>8} {'Threshold':>10} {'Status':>8}"
    lines.append(header)
    lines.append("-" * 78)

    for mod in report.modules:
        status = "PASS" if mod.passing else "BELOW"
        lines.append(
            f"{mod.display_path:<50} {mod.coverage_pct:>7.1f}% {mod.threshold:>9}% {status:>8}"
        )

    lines.append("-" * 78)
    lines.append(f"Summary: {report.total} modules checked, {report.failed} below threshold")
    lines.append("")

    return "\n".join(lines)


def _format_json_report(report: CoverageReport) -> str:
    """Format *report* as JSON for machine consumption."""
    data = {
        "modules": [
            {
                "package": m.package,
                "display_path": m.display_path,
                "coverage_pct": m.coverage_pct,
                "threshold": m.threshold,
                "passing": m.passing,
            }
            for m in report.modules
        ],
        "summary": {
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
        },
    }
    return json.dumps(data, indent=2)


# ── CLI ────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Check per-module coverage against RULE-10 minimums.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  All modules meet thresholds (or --warning-only)\n"
            "  1  At least one module below threshold (--fail only)\n"
            "  2  Coverage XML not found or invalid\n"
            "\n"
            "Thresholds (RULE-10):\n"
            "  packages/core/narrare_core/llm/       95%\n"
            "  packages/core/narrare_core/prompts/    95%\n"
            "  packages/core/narrare_core/* (other)   90%\n"
            "  apps/api/narrare/*                     80%\n"
            "  everything else                        60%\n"
            "\n"
            "Examples:\n"
            "  python scripts/check_module_coverage.py\n"
            "  python scripts/check_module_coverage.py --fail\n"
            "  python scripts/check_module_coverage.py --json\n"
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
        help="Exit 1 if any module is below its threshold (strict mode)",
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

    # ── Parse and analyse ──────────────────────────────────
    try:
        report = parse_coverage_xml(args.coverage_xml)
    except ET.ParseError as exc:
        print(f"Error: Failed to parse {args.coverage_xml}: {exc}", file=sys.stderr)
        return 2

    if not report.modules:
        print("No packages found in coverage XML.", file=sys.stderr)
        return 0

    # ── Output ─────────────────────────────────────────────
    if args.json_output:
        print(_format_json_report(report))
    else:
        print(_format_text_report(report))

    # ── GitHub Actions annotations ─────────────────────────
    for mod in report.modules:
        if not mod.passing:
            annotation = "::error::" if strict else "::warning::"
            print(
                f"{annotation}RULE-10: {mod.display_path} coverage "
                f"{mod.coverage_pct:.1f}% is below {mod.threshold}% threshold"
            )

    # ── Exit code ──────────────────────────────────────────
    if strict and report.failed > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
