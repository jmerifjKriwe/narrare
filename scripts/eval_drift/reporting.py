"""Output formatting for eval drift reports.

Provides human-readable table output and machine-readable JSON output
for eval baseline drift comparisons.

P0 regressions are labelled distinctly (``P0-FAIL``) so a CI-blocking
regression stands out from a non-blocking non-P0 WARNING.

See: docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .comparison import DriftReport

# Exit-mode label passed from the CLI. "P0" = exit code gates only on P0
# regressions; "off" = legacy (any drift is blocking).
_OFF_MODE = "off"


def print_human_report(
    report: DriftReport, threshold: float, priority_mode: str = _OFF_MODE
) -> None:
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
    header = f"{'Test Case':<46} {'Now':>6} {'Base':>6} {'Drift':>7} {'Status':>12}"
    print(header)
    print("-" * len(header))

    for comp in report.comparisons:
        if not comp.baseline_exists:
            status = "NO BASE"
            drift_str = "\u2014"
            base_str = "\u2014"
        elif comp.exceeds_threshold and comp.is_p0:
            status = "\U0001f6d1 P0-FAIL"
            drift_str = f"{comp.drift:+.3f}"
            base_str = f"{comp.baseline_score:.3f}"
        elif comp.exceeds_threshold:
            status = "\u26a0\ufe0f DRIFT"
            drift_str = f"{comp.drift:+.3f}"
            base_str = f"{comp.baseline_score:.3f}"
        else:
            status = "\u2705 OK"
            drift_str = f"{comp.drift:+.3f}"
            base_str = f"{comp.baseline_score:.3f}"

        now_str = f"{comp.current_score:.3f}" if comp.current_score > 0 else "\u2014"
        name = comp.name if len(comp.name) <= 45 else comp.name[:42] + "..."
        print(f"{name:<46} {now_str:>6} {base_str:>6} {drift_str:>7} {status:>12}")

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

    # P0 drift summary (CI-blocking)
    if report.has_p0_drift:
        print(
            f"\U0001f6d1 {report.p0_drift_count} P0 case(s) drifted > {threshold:.0%} (BLOCKING):"
        )
        for comp in report.comparisons:
            if comp.exceeds_threshold and comp.baseline_exists and comp.is_p0:
                print(f"   \u2022 {comp.name}: {comp.drift:+.3f} (threshold: -{threshold:.3f})")
        print()

    # Non-P0 drift summary (WARNING)
    non_p0_drifts = [
        c for c in report.comparisons if c.exceeds_threshold and c.baseline_exists and not c.is_p0
    ]
    if non_p0_drifts:
        blocking_note = "non-blocking" if priority_mode != _OFF_MODE else "blocking"
        print(
            f"\u26a0\ufe0f  {len(non_p0_drifts)} non-P0 case(s) drifted > {threshold:.0%} "
            f"(WARNING, {blocking_note}):"
        )
        for comp in non_p0_drifts:
            print(f"   \u2022 {comp.name}: {comp.drift:+.3f} (threshold: -{threshold:.3f})")
        print()
    elif report.has_baselines and not report.has_drift:
        baseline_count = sum(1 for c in report.comparisons if c.baseline_exists)
        print(
            f"\u2705 All {baseline_count} baseline comparison(s) within "
            f"threshold ({threshold:.0%})."
        )
        print()


def print_json_report(
    report: DriftReport, threshold: float, priority_mode: str = _OFF_MODE
) -> None:
    """Print a JSON-formatted report for CI pipeline consumption."""
    output = {
        "has_drift": report.has_drift,
        "drift_count": report.drift_count,
        "has_p0_drift": report.has_p0_drift,
        "p0_drift_count": report.p0_drift_count,
        "priority_mode": priority_mode,
        "threshold": threshold,
        "comparisons": [
            {
                "name": c.name,
                "current_score": round(c.current_score, 4),
                "baseline_score": round(c.baseline_score, 4) if c.baseline_exists else None,
                "drift": round(c.drift, 4) if c.baseline_exists else None,
                "exceeds_threshold": c.exceeds_threshold if c.baseline_exists else False,
                "baseline_exists": c.baseline_exists,
                "is_p0": c.is_p0,
            }
            for c in report.comparisons
        ],
        "missing_baselines": sorted(set(report.missing_baselines)),
        "errors": report.errors,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
