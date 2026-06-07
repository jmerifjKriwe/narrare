"""Quality metrics models — joining eval results with adoption evidence.

See ADR-041 Decision 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast


@dataclass
class ModeQualityMetric:
    """Quality metric for a single feature mode.

    Joins eval scores, adoption state, and runtime evidence to highlight
    gaps between test performance and adoption.

    Privacy-safe: contains only scores, counts, booleans, and identifiers —
    never eval case content, prompt text, or user data.
    """

    mode: str
    category: str
    adoption_state: str
    static_score: float
    runtime_verified: bool
    eval_score: float | None = None
    eval_drift: float | None = None
    eval_case_count: int = 0
    evidence_count: int = 0
    quality_adoption_gap: bool = False


@dataclass
class QualityReport:
    """Aggregated quality report across all feature modes.

    Summarises how many modes have eval coverage, how many lack it,
    and how many exhibit a quality-adoption gap.
    """

    generated_at: str
    metrics: list[ModeQualityMetric] = field(
        default_factory=lambda: cast("list[ModeQualityMetric]", [])
    )
    modes_with_evals: int = 0
    modes_without_evals: int = 0
    gap_count: int = 0


def build_quality_report(metrics: list[ModeQualityMetric]) -> QualityReport:
    """Build a :class:`QualityReport` from a list of :class:`ModeQualityMetric`.

    Computes summary statistics:
    - ``modes_with_evals`` — metrics that have a non-None ``eval_score``
    - ``modes_without_evals`` — metrics where ``eval_score`` is None
    - ``gap_count`` — metrics where ``quality_adoption_gap`` is True

    Metrics are sorted by ``(category, mode)`` for deterministic output.
    """
    modes_with_evals = sum(1 for m in metrics if m.eval_score is not None)
    modes_without_evals = len(metrics) - modes_with_evals
    gap_count = sum(1 for m in metrics if m.quality_adoption_gap)

    return QualityReport(
        generated_at=datetime.now(tz=UTC).isoformat(),
        metrics=sorted(metrics, key=lambda m: (m.category, m.mode)),
        modes_with_evals=modes_with_evals,
        modes_without_evals=modes_without_evals,
        gap_count=gap_count,
    )
