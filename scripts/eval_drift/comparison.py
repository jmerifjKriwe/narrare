"""Baseline comparison logic for eval drift checking.

Loads stored baselines, compares current eval results against them,
and produces a structured drift report.

See: docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from .parser import BASELINE_VERSION, EvalResultFile, load_json_object

if TYPE_CHECKING:
    from pathlib import Path

# ── Data structures ────────────────────────────────────────────


@dataclass
class DriftComparison:
    """Comparison of a single test case against its baseline."""

    name: str
    current_score: float
    baseline_score: float
    drift: float  # negative = regression
    exceeds_threshold: bool
    baseline_exists: bool


@dataclass
class DriftReport:
    """Aggregated drift report across all result files."""

    comparisons: list[DriftComparison] = field(default_factory=list[DriftComparison])
    missing_baselines: list[str] = field(default_factory=list[str])
    errors: list[str] = field(default_factory=list[str])

    @property
    def has_drift(self) -> bool:
        """True if any baseline comparison exceeds the drift threshold."""
        return any(c.exceeds_threshold for c in self.comparisons if c.baseline_exists)

    @property
    def has_baselines(self) -> bool:
        """True if at least one baseline was found for comparison."""
        return any(c.baseline_exists for c in self.comparisons)

    @property
    def drift_count(self) -> int:
        """Number of test cases exceeding drift threshold."""
        return sum(1 for c in self.comparisons if c.exceeds_threshold and c.baseline_exists)


# ── Baseline I/O ───────────────────────────────────────────────


def load_baseline(
    baselines_dir: Path,
    source: str,
) -> dict[str, Any] | None:
    """Load the baseline file for *source*.

    Returns the parsed baseline dict, or ``None`` if no baseline exists
    or it cannot be parsed.
    """
    baseline_path = baselines_dir / f"{source}-baseline.json"
    return load_json_object(baseline_path)


def update_baselines(
    results: list[EvalResultFile],
    baselines_dir: Path,
) -> list[str]:
    """Write current results as new baseline files.

    Creates the baselines directory if it does not exist.  Returns
    a list of created baseline filenames.
    """
    baselines_dir.mkdir(parents=True, exist_ok=True)
    updated: list[str] = []

    for result_file in results:
        test_cases_data: dict[str, dict[str, Any]] = {}
        for tc in result_file.test_cases:
            test_cases_data[tc.name] = {
                "avg_score": round(tc.avg_score, 4),
                "success_rate": round(tc.success_rate, 4),
                "run_count": tc.run_count,
            }

        baseline_data: dict[str, Any] = {
            "version": BASELINE_VERSION,
            "created_at": datetime.now(tz=UTC).isoformat(),
            "source_file": result_file.source,
            "test_cases": test_cases_data,
            "summary": {
                "avg_score": round(result_file.avg_score, 4),
                "total_test_cases": len(result_file.test_cases),
            },
        }

        baseline_path = baselines_dir / f"{result_file.source}-baseline.json"
        baseline_path.write_text(
            json.dumps(baseline_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        updated.append(baseline_path.name)

    return updated


# ── Comparison logic ───────────────────────────────────────────


def _get_baseline_score(
    baseline_data: dict[str, Any],
    test_case_name: str,
) -> float | None:
    """Look up the baseline score for a named test case.

    Returns ``None`` if no matching baseline entry is found.
    """
    cases_raw = baseline_data.get("test_cases")
    if isinstance(cases_raw, dict):
        cases = cast("dict[str, Any]", cases_raw)
        entry_raw = cases.get(test_case_name)
        if isinstance(entry_raw, dict):
            entry = cast("dict[str, Any]", entry_raw)
            score_raw = entry.get("avg_score")
            if isinstance(score_raw, (int, float)):
                return float(score_raw)

    # Fallback to summary average
    summary_raw = baseline_data.get("summary")
    if isinstance(summary_raw, dict):
        summary = cast("dict[str, Any]", summary_raw)
        fallback_raw = summary.get("avg_score")
        if isinstance(fallback_raw, (int, float)):
            return float(fallback_raw)

    return None


def compare_against_baselines(
    results: list[EvalResultFile],
    baselines_dir: Path,
    threshold: float,
) -> DriftReport:
    """Compare current eval results against stored baselines."""
    report = DriftReport()

    for result_file in results:
        baseline_data = load_baseline(baselines_dir, result_file.source)

        if baseline_data is None:
            # No baseline -- record current results for visibility
            report.missing_baselines.append(result_file.source)
            for tc in result_file.test_cases:
                report.comparisons.append(
                    DriftComparison(
                        name=f"{result_file.source} :: {tc.name}",
                        current_score=tc.avg_score,
                        baseline_score=0.0,
                        drift=0.0,
                        exceeds_threshold=False,
                        baseline_exists=False,
                    )
                )
            continue

        for tc in result_file.test_cases:
            baseline_score = _get_baseline_score(baseline_data, tc.name)

            if baseline_score is None:
                baseline_score = 0.0
                report.missing_baselines.append(f"{result_file.source} :: {tc.name}")

            drift = tc.avg_score - baseline_score

            report.comparisons.append(
                DriftComparison(
                    name=f"{result_file.source} :: {tc.name}",
                    current_score=tc.avg_score,
                    baseline_score=baseline_score,
                    drift=drift,
                    exceeds_threshold=drift < -threshold,
                    baseline_exists=True,
                )
            )

    return report
