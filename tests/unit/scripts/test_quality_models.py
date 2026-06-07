"""Tests for quality metrics models — ModeQualityMetric, QualityReport, gap detection.

See ADR-041 Decision 3.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

# Ensure scripts/ is on sys.path for package imports.
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from quality.joiner import _detect_gap  # noqa: E402
from quality.quality_report import ModeQualityMetric, build_quality_report  # noqa: E402


class TestModeQualityMetric:
    """ModeQualityMetric construction."""

    def test_basic_creation(self) -> None:
        """Minimal ModeQualityMetric can be created."""
        m = ModeQualityMetric(
            mode="new_chapter",
            category="writing",
            adoption_state="adopted",
            static_score=0.95,
            runtime_verified=True,
        )
        assert m.mode == "new_chapter"
        assert m.category == "writing"
        assert m.adoption_state == "adopted"
        assert m.static_score == 0.95
        assert m.runtime_verified is True
        assert m.eval_score is None
        assert m.eval_drift is None
        assert m.eval_case_count == 0
        assert m.evidence_count == 0
        assert m.quality_adoption_gap is False

    def test_with_eval_data(self) -> None:
        """ModeQualityMetric with eval scores."""
        m = ModeQualityMetric(
            mode="general",
            category="analysis",
            adoption_state="static_verified",
            static_score=0.75,
            runtime_verified=False,
            eval_score=0.92,
            eval_drift=0.0,
            eval_case_count=5,
            evidence_count=3,
            quality_adoption_gap=True,
        )
        assert m.eval_score == 0.92
        assert m.eval_drift == 0.0
        assert m.eval_case_count == 5
        assert m.evidence_count == 3
        assert m.quality_adoption_gap is True


class TestQualityReport:
    """QualityReport building and stats."""

    def test_empty_report(self) -> None:
        """Empty metrics produce zeroed report."""
        report = build_quality_report([])
        assert report.metrics == []
        assert report.modes_with_evals == 0
        assert report.modes_without_evals == 0
        assert report.gap_count == 0
        assert report.generated_at is not None

    def test_report_with_metrics(self) -> None:
        """Report computes correct summary stats."""
        metrics = [
            ModeQualityMetric(
                mode="a",
                category="cat",
                adoption_state="adopted",
                static_score=0.9,
                runtime_verified=True,
                eval_score=0.95,
                eval_case_count=3,
                quality_adoption_gap=False,
            ),
            ModeQualityMetric(
                mode="b",
                category="cat",
                adoption_state="identified",
                static_score=0.5,
                runtime_verified=False,
                quality_adoption_gap=False,
            ),
            ModeQualityMetric(
                mode="c",
                category="cat",
                adoption_state="static_verified",
                static_score=0.8,
                runtime_verified=False,
                eval_score=0.95,
                eval_case_count=5,
                quality_adoption_gap=True,
            ),
        ]
        report = build_quality_report(metrics)
        assert report.modes_with_evals == 2
        assert report.modes_without_evals == 1
        assert report.gap_count == 1

    def test_metrics_sorted(self) -> None:
        """Metrics are sorted by (category, mode)."""
        metrics = [
            ModeQualityMetric(
                mode="z",
                category="writing",
                adoption_state="adopted",
                static_score=0.9,
                runtime_verified=True,
            ),
            ModeQualityMetric(
                mode="a",
                category="writing",
                adoption_state="adopted",
                static_score=0.9,
                runtime_verified=True,
            ),
            ModeQualityMetric(
                mode="a",
                category="analysis",
                adoption_state="adopted",
                static_score=0.9,
                runtime_verified=True,
            ),
        ]
        report = build_quality_report(metrics)
        assert report.metrics[0].category == "analysis"
        assert report.metrics[0].mode == "a"
        assert report.metrics[1].category == "writing"
        assert report.metrics[1].mode == "a"
        assert report.metrics[2].category == "writing"
        assert report.metrics[2].mode == "z"


class TestGapDetection:
    """_detect_gap logic."""

    def test_no_gap_eval_none(self) -> None:
        """No gap when eval_score is None."""
        assert _detect_gap(None, 0.9) is False

    def test_no_gap_aligned_high(self) -> None:
        """No gap when both are high."""
        assert _detect_gap(0.95, 0.9) is False

    def test_no_gap_aligned_low(self) -> None:
        """No gap when both are low."""
        assert _detect_gap(0.5, 0.6) is False

    def test_gap_eval_high_adoption_low(self) -> None:
        """Gap: eval > 0.7 but adoption < 0.85."""
        assert _detect_gap(0.95, 0.6) is True

    def test_gap_eval_low_adoption_high(self) -> None:
        """Gap: eval < 0.7 but adoption > 0.85."""
        assert _detect_gap(0.5, 0.9) is True

    def test_edge_eval_at_threshold(self) -> None:
        """No gap when eval is exactly at threshold."""
        assert _detect_gap(0.7, 0.5) is False
        assert _detect_gap(0.5, 0.85) is False


class TestReportSerialization:
    """QualityReport JSON serialization."""

    def test_asdict_roundtrip(self) -> None:
        """Dataclass asdict produces a serializable dict."""
        m = ModeQualityMetric(
            mode="new_chapter",
            category="writing",
            adoption_state="adopted",
            static_score=0.9,
            runtime_verified=True,
            eval_score=0.95,
            eval_case_count=5,
            evidence_count=3,
        )
        report = build_quality_report([m])
        data = asdict(report)
        assert isinstance(data, dict)
        assert "generated_at" in data
        assert len(data["metrics"]) == 1
        # Round-trip through JSON
        roundtrip = json.loads(json.dumps(data, default=str))
        assert roundtrip["modes_with_evals"] == 1
        assert roundtrip["modes_without_evals"] == 0
        assert roundtrip["gap_count"] == 0
