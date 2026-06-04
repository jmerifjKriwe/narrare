"""Output formatting for eval drift reports.

Provides human-readable table output and machine-readable JSON output
for eval baseline drift comparisons.

See: docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .comparison import DriftReport


def print_human_report(report: DriftReport, threshold: float) -> None:
    """Print a human-readable drift report to stdout."""
    print("=" * 72)
    print("  NARRARE EVAL BASELINE DRIFT CHECKER")
    print("=" * 72)
    print()

    if not report.comparisons:
        print("No eval results found to compare.")
        print()
        return

    # Summary table
    header = f"{'Test Case':<48} {'Now':>6} {'Base':>6} {'Drift':>7} {'Status':>9}"
    print(header)
    print("-" * len(header))

    for comp in report.comparisons:
        if not comp.baseline_exists:
            status = "NO BASE"
            drift_str = "\u2014"
            base_str = "\u2014"
        elif comp.exceeds_threshold:
            status = "\u274c DRIFT"
            drift_str = f"{comp.drift:+.3f}"
            base_str = f"{comp.baseline_score:.3f}"
        else:
            status = "\u2705 OK"
            drift_str = f"{comp.drift:+.3f}"
            base_str = f"{comp.baseline_score:.3f}"

        now_str = f"{comp.current_score:.3f}" if comp.current_score > 0 else "\u2014"
        name = comp.name if len(comp.name) <= 47 else comp.name[:44] + "..."
        print(f"{name:<48} {now_str:>6} {base_str:>6} {drift_str:>7} {status:>9}")

    print()

    # Baseline status
    if report.missing_baselines:
        unique_missing = sorted(set(report.missing_baselines))
        print(f"\u2139\ufe0f  {len(unique_missing)} test config(s) have no baseline:")
        for name in unique_missing:
            print(f"   \u2022 {name}")
        print()
        print("   Run with --update-baselines to create initial baselines.")
        print()

    # Drift summary
    if report.has_drift:
        print(f"\u274c {report.drift_count} test case(s) show drift > {threshold:.0%}:")
        for comp in report.comparisons:
            if comp.exceeds_threshold and comp.baseline_exists:
                print(f"   \u2022 {comp.name}: {comp.drift:+.3f} (threshold: -{threshold:.3f})")
        print()
    elif report.has_baselines:
        baseline_count = sum(1 for c in report.comparisons if c.baseline_exists)
        print(
            f"\u2705 All {baseline_count} baseline comparison(s) within "
            f"threshold ({threshold:.0%})."
        )
        print()


def print_json_report(report: DriftReport, threshold: float) -> None:
    """Print a JSON-formatted report for CI pipeline consumption."""
    output = {
        "has_drift": report.has_drift,
        "drift_count": report.drift_count,
        "threshold": threshold,
        "comparisons": [
            {
                "name": c.name,
                "current_score": round(c.current_score, 4),
                "baseline_score": round(c.baseline_score, 4) if c.baseline_exists else None,
                "drift": round(c.drift, 4) if c.baseline_exists else None,
                "exceeds_threshold": c.exceeds_threshold if c.baseline_exists else False,
                "baseline_exists": c.baseline_exists,
            }
            for c in report.comparisons
        ],
        "missing_baselines": sorted(set(report.missing_baselines)),
        "errors": report.errors,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
