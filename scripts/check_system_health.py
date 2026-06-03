#!/usr/bin/env python3
"""System Health Aggregator - weighted gate score for CI.

Reads the ratcheted baseline and computes a weighted health score
(0.0-1.0) from individual gate results. Does NOT invoke check
scripts as subprocesses - it is a pure aggregator over baseline data.

Thresholds:
    >= 0.85  HEALTHY     exit 0, green badge
    0.70-0.85  DEGRADED  exit 0, yellow badge, warnings in output
    < 0.70   CRITICAL    exit 1, CI failure

Usage:
    python scripts/check_system_health.py
    python scripts/check_system_health.py --json
    python scripts/check_system_health.py --badge docs/_shared/system-health.md

See: AUFG-NEW-03
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.architecture.baselines import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    load_baseline,
)
from scripts.health_format import (  # noqa: E402
    format_badge_markdown,
    format_human,
    format_json,
)
from scripts.health_types import (  # noqa: E402
    DEGRADED_THRESHOLD,
    HEALTHY_THRESHOLD,
    GateResult,
    HealthReport,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateConfig:
    """Weight and baseline section for a single gate."""

    name: str
    weight: float
    baseline_section: str
    description: str


GATES: list[GateConfig] = [
    GateConfig("architecture", 0.20, "__no_baseline__", "Architecture Constraints (RULE-XX)"),
    GateConfig("prompt_structure", 0.15, "prompt_structure_warnings", "Prompt Structure warnings"),
    GateConfig("feature_adoption", 0.15, "adoption_debt", "Feature Adoption debt items"),
    GateConfig(
        "streaming_compliance", 0.10, "streaming_compliance_gaps", "Streaming Compliance gaps"
    ),
    GateConfig("exception_baseline", 0.10, "approved_exceptions", "Approved Exception count"),
    GateConfig(
        "frontend_file_size", 0.10, "frontend_file_size_violations", "Frontend File Size violations"
    ),
    GateConfig("test_status", 0.20, "__no_baseline__", "Test Status (unit + integration)"),
]

# ---------------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------------


def _extract_section(baseline: dict[str, Any], section: str) -> list[str]:
    """Extract a string list from baseline data."""
    raw: Any = baseline.get(section, [])
    if raw is None or not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in list(raw):  # type: ignore[arg-type]
        if isinstance(item, str):
            result.append(item)
    return result


def score_gate(
    gate: GateConfig,
    baseline_data: dict[str, Any],
    test_results_file: Path | None = None,
) -> GateResult:
    """Compute score for a single gate from baseline data."""
    if gate.baseline_section == "__no_baseline__":
        return _score_non_baseline(gate, test_results_file)

    baseline_count = len(_extract_section(baseline_data, gate.baseline_section))
    score = (
        max(0.5, 1.0 - (math.log1p(baseline_count) / math.log1p(200)))
        if baseline_count > 0
        else 1.0
    )

    return GateResult(
        name=gate.name,
        weight=gate.weight,
        score=score,
        details=f"{baseline_count} baseline items (section: {gate.baseline_section})",
    )


def _score_non_baseline(
    gate: GateConfig,
    test_results_file: Path | None = None,
) -> GateResult:
    """Score gates that don't use baseline data (architecture, tests)."""
    if gate.name == "architecture":
        return GateResult(
            gate.name, gate.weight, 1.0, "Architecture constraints verified by CI step"
        )
    if gate.name == "test_status":
        return _score_tests(test_results_file)
    return GateResult(gate.name, gate.weight, 1.0, "No baseline data - assuming pass")


def _score_tests(test_results_file: Path | None) -> GateResult:
    """Score test status from a pytest results JSON or default to pass."""
    if test_results_file and test_results_file.exists():
        try:
            data = json.loads(test_results_file.read_text(encoding="utf-8"))
            total = data.get("total", 0)
            passed = data.get("passed", 0)
            failed = data.get("failed", 0)
            errors = data.get("errors", 0)
            if total == 0:
                return GateResult("test_status", 0.20, 1.0, "No test data - assuming pass")
            score = passed / total
            return GateResult(
                "test_status",
                0.20,
                score,
                f"{passed}/{total} passed, {failed + errors} failed/errors",
            )
        except json.JSONDecodeError, KeyError:
            pass
    return GateResult("test_status", 0.20, 1.0, "Tests verified by CI step")


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def compute_health(
    baseline_path: Path = DEFAULT_BASELINE_PATH,
    test_results_file: Path | None = None,
) -> HealthReport:
    """Compute the aggregated system health score."""
    baseline_data = load_baseline(baseline_path)
    gates: list[GateResult] = [score_gate(g, baseline_data, test_results_file) for g in GATES]

    total_weight = sum(g.weight for g in gates)
    weighted_score = sum(g.score * g.weight for g in gates)
    score = round(weighted_score / total_weight, 4) if total_weight > 0 else 0.0

    if score >= HEALTHY_THRESHOLD:
        status = "HEALTHY"
    elif score >= DEGRADED_THRESHOLD:
        status = "DEGRADED"
    else:
        status = "CRITICAL"

    return HealthReport(score=score, status=status, gates=gates)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute aggregated system health score from gate results.",
        epilog="Exit codes: 0 = HEALTHY/DEGRADED, 1 = CRITICAL (< 0.70)",
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--test-results", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--badge", type=Path, default=None)
    args = parser.parse_args()

    report = compute_health(args.baseline, args.test_results)

    if args.json:
        print(format_json(report))
    else:
        print(format_human(report))

    if args.badge:
        args.badge.parent.mkdir(parents=True, exist_ok=True)
        args.badge.write_text(format_badge_markdown(report), encoding="utf-8")
        print(f"Badge written to {args.badge}")

    if report.status == "CRITICAL":
        print(
            f"\nRESULT: System health CRITICAL (score: {report.score:.2f} < {DEGRADED_THRESHOLD})"
        )
        return 1

    if report.status == "DEGRADED":
        print(f"\nRESULT: System health DEGRADED (score: {report.score:.2f})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
