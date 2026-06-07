"""Tests for quality metrics joiner — join, gap detection, eval matching, evidence.

See ADR-041 Decision 3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from quality.joiner import join_quality_metrics, parse_evidence_lines  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def evidence_dir(tmp_path: Path) -> Path:
    ev_dir = tmp_path / ".evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    return ev_dir


def write_evidence(evidence_dir: Path, records: list[dict[str, object]]) -> Path:
    path = evidence_dir / "invocations.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return path


# ── Empty join ────────────────────────────────────────────────────


class TestJoinEmpty:
    """Joiner behaviour with no data."""

    def test_no_adoption_report(self) -> None:
        assert join_quality_metrics(None, None, [], []) == []

    def test_empty_adoption(self) -> None:
        from adoption.scorer import AdoptionReport

        adoption = AdoptionReport(overall_score=1.0, status="PASS")
        assert join_quality_metrics(adoption, None, [], []) == []


# ── Basic join ────────────────────────────────────────────────────


class TestJoinBasic:
    """Join single mode with all data sources."""

    def test_single_mode_no_evals(self) -> None:
        """Single mode with adoption data but no evals."""
        from adoption.scorer import AdoptionReport, CategoryScore
        from adoption.scorer_modes import ModeScore

        ms = ModeScore(
            mode="new_chapter",
            score=0.9,
            status="PASS",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
        )
        cat = CategoryScore(category="writing", score=0.9, status="PASS", modes=[ms])
        adoption = AdoptionReport(overall_score=0.9, status="PASS", categories=[cat])
        metrics = join_quality_metrics(adoption, None, [], [])
        assert len(metrics) == 1
        m = metrics[0]
        assert m.mode == "new_chapter" and m.category == "writing"
        assert m.static_score == 0.9 and m.runtime_verified is True
        assert m.eval_score is None and m.eval_case_count == 0
        assert m.evidence_count == 0 and m.adoption_state == "identified"

    def test_with_audit_state(self) -> None:
        """Audit state is picked up from AuditReport."""
        from adoption.audit_report import AuditReport, AuditTransition, ModeAuditState
        from adoption.scorer import AdoptionReport, CategoryScore
        from adoption.scorer_modes import ModeScore

        ms = ModeScore(
            mode="new_chapter",
            score=0.9,
            status="PASS",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
        )
        cat = CategoryScore(category="writing", score=0.9, status="PASS", modes=[ms])
        adoption = AdoptionReport(overall_score=0.9, status="PASS", categories=[cat])
        audit = AuditReport(
            generated_at="2026-06-07T00:00:00",
            modes=[
                ModeAuditState(
                    mode="new_chapter",
                    category="writing",
                    current_state="adopted",
                    transitions=[
                        AuditTransition(
                            state="adopted",
                            timestamp="2026-06-07T00:00:00",
                            evidence_id="adopted:writing/new_chapter",
                            reason="static + runtime verified, adopted=True",
                        )
                    ],
                )
            ],
        )
        metrics = join_quality_metrics(adoption, audit, [], [])
        assert len(metrics) == 1 and metrics[0].adoption_state == "adopted"

    def test_with_evidence(self) -> None:
        """Evidence counts are matched per (category, mode)."""
        from adoption.scorer import AdoptionReport, CategoryScore
        from adoption.scorer_modes import ModeScore

        ms = ModeScore(
            mode="new_chapter",
            score=0.9,
            status="PASS",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
        )
        cat = CategoryScore(category="writing", score=0.9, status="PASS", modes=[ms])
        adoption = AdoptionReport(overall_score=0.9, status="PASS", categories=[cat])
        evidence = [
            {
                "feature_id": "writing/new_chapter",
                "mode": "new_chapter",
                "intent": "continue_session",
                "audit_state": "adopted",
            },
            {
                "feature_id": "writing/new_chapter",
                "mode": "new_chapter",
                "intent": "regenerate",
                "audit_state": "adopted",
            },
            {
                "feature_id": "analysis/general",
                "mode": "general",
                "intent": "analyze",
                "audit_state": "adopted",
            },
        ]
        metrics = join_quality_metrics(adoption, None, [], evidence)
        assert len(metrics) == 1 and metrics[0].evidence_count == 2


class TestJoinGapDetection:
    """Gap detection in joined metrics."""

    def test_eval_high_adoption_low_gap(self) -> None:
        """Gap: eval high, adoption low."""
        from adoption.scorer import AdoptionReport, CategoryScore
        from adoption.scorer_modes import ModeScore
        from eval_drift.parser import EvalResultFile, TestCaseScore

        ms = ModeScore(
            mode="general",
            score=0.6,
            status="WARN",
            static_verified=False,
            runtime_verified=False,
            adopted=False,
        )
        cat = CategoryScore(category="analysis", score=0.6, status="WARN", modes=[ms])
        adoption = AdoptionReport(overall_score=0.6, status="WARN", categories=[cat])
        ev = EvalResultFile(source="general", test_cases=[TestCaseScore(name="t1", scores=[0.95])])
        metrics = join_quality_metrics(adoption, None, [ev], [])
        assert metrics[0].eval_score == 0.95
        assert metrics[0].static_score == 0.6
        assert metrics[0].quality_adoption_gap is True

    def test_eval_low_adoption_high_gap(self) -> None:
        """Gap: eval low, adoption high."""
        from adoption.scorer import AdoptionReport, CategoryScore
        from adoption.scorer_modes import ModeScore
        from eval_drift.parser import EvalResultFile, TestCaseScore

        ms = ModeScore(
            mode="new_chapter",
            score=0.9,
            status="PASS",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
        )
        cat = CategoryScore(category="writing", score=0.9, status="PASS", modes=[ms])
        adoption = AdoptionReport(overall_score=0.9, status="PASS", categories=[cat])
        ev = EvalResultFile(
            source="writing-new_chapter", test_cases=[TestCaseScore(name="t1", scores=[0.4])]
        )
        metrics = join_quality_metrics(adoption, None, [ev], [])
        assert metrics[0].quality_adoption_gap is True

    def test_no_gap(self) -> None:
        """No gap when eval and adoption are aligned."""
        from adoption.scorer import AdoptionReport, CategoryScore
        from adoption.scorer_modes import ModeScore
        from eval_drift.parser import EvalResultFile, TestCaseScore

        ms = ModeScore(
            mode="new_chapter",
            score=0.9,
            status="PASS",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
        )
        cat = CategoryScore(category="writing", score=0.9, status="PASS", modes=[ms])
        adoption = AdoptionReport(overall_score=0.9, status="PASS", categories=[cat])
        ev = EvalResultFile(
            source="writing-new_chapter", test_cases=[TestCaseScore(name="t1", scores=[0.95])]
        )
        metrics = join_quality_metrics(adoption, None, [ev], [])
        assert metrics[0].quality_adoption_gap is False


class TestJoinEvalMatching:
    """Eval mode matching strategies."""

    def test_match_by_mode_name(self) -> None:
        """Eval matching by direct mode name."""
        from adoption.scorer import AdoptionReport, CategoryScore
        from adoption.scorer_modes import ModeScore
        from eval_drift.parser import EvalResultFile, TestCaseScore

        ms = ModeScore(
            mode="general",
            score=0.5,
            status="FAIL",
            static_verified=False,
            runtime_verified=False,
            adopted=False,
        )
        cat = CategoryScore(category="analysis", score=0.5, status="FAIL", modes=[ms])
        adoption = AdoptionReport(overall_score=0.5, status="FAIL", categories=[cat])
        ev = EvalResultFile(source="general", test_cases=[TestCaseScore(name="t1", scores=[0.8])])
        metrics = join_quality_metrics(adoption, None, [ev], [])
        assert metrics[0].eval_score == 0.8

    def test_match_by_category_mode(self) -> None:
        """Eval matching by category-mode pattern."""
        from adoption.scorer import AdoptionReport, CategoryScore
        from adoption.scorer_modes import ModeScore
        from eval_drift.parser import EvalResultFile, TestCaseScore

        ms = ModeScore(
            mode="new_chapter",
            score=0.9,
            status="PASS",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
        )
        cat = CategoryScore(category="writing", score=0.9, status="PASS", modes=[ms])
        adoption = AdoptionReport(overall_score=0.9, status="PASS", categories=[cat])
        ev = EvalResultFile(
            source="writing-new_chapter", test_cases=[TestCaseScore(name="t1", scores=[0.9])]
        )
        metrics = join_quality_metrics(adoption, None, [ev], [])
        assert metrics[0].eval_score == 0.9

    def test_no_match_returns_none(self) -> None:
        """Non-matching eval source results in None eval_score."""
        from adoption.scorer import AdoptionReport, CategoryScore
        from adoption.scorer_modes import ModeScore
        from eval_drift.parser import EvalResultFile, TestCaseScore

        ms = ModeScore(
            mode="new_chapter",
            score=0.9,
            status="PASS",
            static_verified=True,
            runtime_verified=True,
            adopted=True,
        )
        cat = CategoryScore(category="writing", score=0.9, status="PASS", modes=[ms])
        adoption = AdoptionReport(overall_score=0.9, status="PASS", categories=[cat])
        ev = EvalResultFile(
            source="unrelated-eval", test_cases=[TestCaseScore(name="t1", scores=[0.9])]
        )
        metrics = join_quality_metrics(adoption, None, [ev], [])
        assert metrics[0].eval_score is None


# ── Evidence parsing ─────────────────────────────────────────────


class TestParseEvidenceLines:
    """parse_evidence_lines behaviour."""

    def test_parse_valid_jsonl(self, evidence_dir: Path) -> None:
        write_evidence(
            evidence_dir,
            [
                {
                    "feature_id": "writing/new_chapter",
                    "mode": "new_chapter",
                    "intent": "continue",
                    "audit_state": "adopted",
                },
                {
                    "feature_id": "analysis/general",
                    "mode": "general",
                    "intent": "analyze",
                    "audit_state": "static_verified",
                },
            ],
        )
        records = parse_evidence_lines(evidence_dir / "invocations.jsonl")
        assert len(records) == 2
        assert records[0]["feature_id"] == "writing/new_chapter"
        assert records[1]["audit_state"] == "static_verified"

    def test_parse_empty_file(self, evidence_dir: Path) -> None:
        path = evidence_dir / "invocations.jsonl"
        path.write_text("", encoding="utf-8")
        assert parse_evidence_lines(path) == []

    def test_parse_skips_blank_lines(self, evidence_dir: Path) -> None:
        write_evidence(
            evidence_dir,
            [
                {
                    "feature_id": "writing/new_chapter",
                    "mode": "new_chapter",
                    "intent": "continue",
                    "audit_state": "adopted",
                },
            ],
        )
        path = evidence_dir / "invocations.jsonl"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n")
            fh.write("not-json\n")
        assert len(parse_evidence_lines(path)) == 1

    def test_parse_with_timestamp(self, evidence_dir: Path) -> None:
        write_evidence(
            evidence_dir,
            [
                {
                    "feature_id": "writing/new_chapter",
                    "mode": "new_chapter",
                    "intent": "continue",
                    "audit_state": "adopted",
                    "timestamp": "2026-06-07T12:00:00",
                },
            ],
        )
        records = parse_evidence_lines(evidence_dir / "invocations.jsonl")
        assert len(records) == 1
        assert records[0]["timestamp"] == "2026-06-07T12:00:00"

    def test_missing_file(self, tmp_path: Path) -> None:
        assert parse_evidence_lines(tmp_path / "nonexistent.jsonl") == []

    def test_invalid_directory(self, tmp_path: Path) -> None:
        assert parse_evidence_lines(tmp_path) == []
