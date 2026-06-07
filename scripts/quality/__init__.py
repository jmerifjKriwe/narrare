"""Narrare Quality Metrics — eval + evidence + adoption correlation.

Joins Pydantic Eval results with adoption/audit reports and invocation
evidence to produce per-mode quality metrics and highlight gaps between
test performance and adoption state.

See ADR-041 Decision 3.
"""

from quality.joiner import join_quality_metrics, parse_evidence_lines
from quality.quality_report import ModeQualityMetric, QualityReport, build_quality_report

__all__ = [
    "ModeQualityMetric",
    "QualityReport",
    "build_quality_report",
    "join_quality_metrics",
    "parse_evidence_lines",
]
