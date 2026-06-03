"""Tests for scripts/check_system_health.py.

Validates score computation, threshold classification, gate scoring
heuristics, and output formatting.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scripts.architecture.baselines import DEFAULT_BASELINE_PATH  # noqa: E402
from scripts.check_system_health import (  # noqa: E402
    GATES,
    GateConfig,
    compute_health,
    score_gate,
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

# ── Helpers ────────────────────────────────────────────────────────


def _gate(name: str) -> GateConfig:
    """Look up a gate by name."""
    for gate in GATES:
        if gate.name == name:
            return gate
    raise ValueError(f"Unknown gate: {name}")


def _report(score: float) -> HealthReport:
    """Create a HealthReport with a single gate producing the given score."""
    if score >= HEALTHY_THRESHOLD:
        status = "HEALTHY"
    elif score >= DEGRADED_THRESHOLD:
        status = "DEGRADED"
    else:
        status = "CRITICAL"
    return HealthReport(
        score=score,
        status=status,
        gates=[GateResult(name="test_gate", weight=1.0, score=score)],
    )


# ── Score computation ──────────────────────────────────────────────


class TestComputeHealth:
    """Tests for the compute_health function."""

    def test_empty_baseline_produces_healthy(self, tmp_path: Path) -> None:
        """An empty baseline means all debt is zero → HEALTHY."""
        baseline = tmp_path / "baseline.json"
        baseline.write_text("{}", encoding="utf-8")
        report = compute_health(baseline)
        assert report.status == "HEALTHY"
        assert report.score >= HEALTHY_THRESHOLD

    def test_real_baseline_produces_report(self) -> None:
        """The actual project baseline should produce a valid report."""
        report = compute_health(DEFAULT_BASELINE_PATH)
        assert 0.0 <= report.score <= 1.0
        assert report.status in {"HEALTHY", "DEGRADED", "CRITICAL"}
        assert len(report.gates) == len(GATES)

    def test_weighted_score_calculation(self, tmp_path: Path) -> None:
        """Verify weighted average is computed correctly."""
        baseline = tmp_path / "baseline.json"
        baseline.write_text(
            json.dumps(
                {
                    "prompt_structure_warnings": ["a"] * 200,
                    "adoption_debt": ["b"] * 200,
                    "streaming_compliance_gaps": ["c"] * 200,
                    "approved_exceptions": ["d"] * 200,
                    "frontend_file_size_violations": ["e"] * 200,
                }
            ),
            encoding="utf-8",
        )
        report = compute_health(baseline)
        # All baseline sections have 200 items → high debt → score should be low
        assert report.score < HEALTHY_THRESHOLD

    def test_weights_sum_to_one(self) -> None:
        """Gate weights should sum to approximately 1.0."""
        total = sum(g.weight for g in GATES)
        assert abs(total - 1.0) < 0.001


class TestScoreGate:
    """Tests for individual gate scoring."""

    def test_non_baseline_gate_scores_1(self) -> None:
        """Architecture gate (no baseline) scores 1.0."""
        gate = _gate("architecture")
        result = score_gate(gate, {})
        assert result.score == 1.0

    def test_empty_section_scores_high(self) -> None:
        """A gate with zero baseline items should score well."""
        gate = _gate("prompt_structure")
        baseline: dict[str, list[str]] = {"prompt_structure_warnings": []}
        result = score_gate(gate, baseline)
        assert result.score >= 0.5

    def test_many_debt_items_scores_lower(self) -> None:
        """More debt items → lower score."""
        gate = _gate("prompt_structure")
        low_debt: dict[str, list[str]] = {"prompt_structure_warnings": ["a"]}
        high_debt: dict[str, list[str]] = {
            "prompt_structure_warnings": [f"x{i}" for i in range(100)]
        }
        low_result = score_gate(gate, low_debt)
        high_result = score_gate(gate, high_debt)
        assert low_result.score > high_result.score

    def test_test_status_with_results_file(self, tmp_path: Path) -> None:
        """Test gate scores from a results JSON file."""
        gate = _gate("test_status")
        results = tmp_path / "results.json"
        results.write_text(
            json.dumps({"total": 100, "passed": 80, "failed": 20, "errors": 0}),
            encoding="utf-8",
        )
        result = score_gate(gate, {}, results)
        assert result.score == 0.8

    def test_test_status_all_pass(self, tmp_path: Path) -> None:
        """All tests passing → score 1.0."""
        gate = _gate("test_status")
        results = tmp_path / "results.json"
        results.write_text(
            json.dumps({"total": 50, "passed": 50, "failed": 0, "errors": 0}),
            encoding="utf-8",
        )
        result = score_gate(gate, {}, results)
        assert result.score == 1.0

    def test_test_status_no_file_defaults_to_pass(self) -> None:
        """No results file → default score 1.0 (CI already verified)."""
        gate = _gate("test_status")
        result = score_gate(gate, {})
        assert result.score == 1.0


# ── Threshold classification ───────────────────────────────────────


class TestThresholds:
    """Tests for HEALTHY / DEGRADED / CRITICAL classification."""

    def test_healthy_threshold(self) -> None:
        """Score at healthy threshold → HEALTHY."""
        report = _report(0.85)
        assert report.status == "HEALTHY"

    def test_above_healthy(self) -> None:
        """Score above healthy threshold → HEALTHY."""
        report = _report(0.90)
        assert report.status == "HEALTHY"

    def test_degraded_boundary(self) -> None:
        """Score at degraded lower boundary → DEGRADED."""
        report = _report(0.70)
        assert report.status == "DEGRADED"

    def test_degraded_middle(self) -> None:
        """Score in degraded range → DEGRADED."""
        report = _report(0.77)
        assert report.status == "DEGRADED"

    def test_critical(self) -> None:
        """Score below degraded threshold → CRITICAL."""
        report = _report(0.69)
        assert report.status == "CRITICAL"

    def test_critical_zero(self) -> None:
        """Score of zero → CRITICAL."""
        report = _report(0.0)
        assert report.status == "CRITICAL"

    def test_perfect_score(self) -> None:
        """Perfect score → HEALTHY."""
        report = _report(1.0)
        assert report.status == "HEALTHY"


# ── Exit codes ─────────────────────────────────────────────────────


class TestExitCodes:
    """Tests for exit code logic."""

    def test_healthy_exit_zero(self) -> None:
        report = _report(0.90)
        assert report.exit_code == 0

    def test_degraded_exit_zero(self) -> None:
        report = _report(0.75)
        assert report.exit_code == 0

    def test_critical_exit_one(self) -> None:
        report = _report(0.50)
        assert report.exit_code == 1


# ── Output formatting ──────────────────────────────────────────────


class TestFormatHuman:
    """Tests for human-readable output."""

    def test_includes_score(self) -> None:
        report = _report(0.85)
        output = format_human(report)
        assert "0.85" in output
        assert "HEALTHY" in output

    def test_includes_gate_names(self) -> None:
        report = _report(0.85)
        output = format_human(report)
        assert "test_gate" in output

    def test_degraded_includes_warning(self) -> None:
        report = _report(0.75)
        output = format_human(report)
        assert "DEGRADED" in output

    def test_critical_includes_failure(self) -> None:
        report = _report(0.50)
        output = format_human(report)
        assert "CRITICAL" in output


class TestFormatJson:
    """Tests for JSON output."""

    def test_valid_json(self) -> None:
        report = _report(0.85)
        output = format_json(report)
        data = json.loads(output)
        assert data["score"] == 0.85
        assert data["status"] == "HEALTHY"

    def test_includes_thresholds(self) -> None:
        report = _report(0.85)
        output = format_json(report)
        data = json.loads(output)
        assert data["thresholds"]["healthy"] == HEALTHY_THRESHOLD
        assert data["thresholds"]["degraded"] == DEGRADED_THRESHOLD

    def test_includes_gates(self) -> None:
        report = _report(0.85)
        output = format_json(report)
        data = json.loads(output)
        assert len(data["gates"]) == 1
        assert data["gates"][0]["name"] == "test_gate"


class TestFormatBadgeMarkdown:
    """Tests for Markdown badge file."""

    def test_includes_score(self) -> None:
        report = _report(0.85)
        md = format_badge_markdown(report)
        assert "0.85" in md
        assert "HEALTHY" in md

    def test_includes_badge_url(self) -> None:
        report = _report(0.85)
        md = format_badge_markdown(report)
        assert "img.shields.io" in md

    def test_includes_gate_table(self) -> None:
        report = _report(0.85)
        md = format_badge_markdown(report)
        assert "| test_gate" in md

    def test_critical_uses_red(self) -> None:
        report = _report(0.50)
        md = format_badge_markdown(report)
        assert "red" in md

    def test_degraded_uses_yellow(self) -> None:
        report = _report(0.75)
        md = format_badge_markdown(report)
        assert "yellow" in md


# ── Edge cases ─────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases for robustness."""

    def test_missing_baseline_file(self, tmp_path: Path) -> None:
        """Missing baseline → should still produce a report."""
        missing = tmp_path / "nonexistent.json"
        report = compute_health(missing)
        assert report.score > 0.0
        assert report.status in {"HEALTHY", "DEGRADED", "CRITICAL"}

    def test_corrupt_results_json(self, tmp_path: Path) -> None:
        """Corrupt test results JSON → defaults to pass."""
        gate = _gate("test_status")
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json at all", encoding="utf-8")
        result = score_gate(gate, {}, bad_file)
        assert result.score == 1.0  # Falls back to default

    def test_results_missing_keys(self, tmp_path: Path) -> None:
        """Test results with missing keys → defaults to pass."""
        gate = _gate("test_status")
        results = tmp_path / "results.json"
        results.write_text(json.dumps({}), encoding="utf-8")
        result = score_gate(gate, {}, results)
        # total=0 → returns 1.0 (no test data)
        assert result.score == 1.0

    def test_all_gates_have_valid_weight(self) -> None:
        """Every gate should have a weight between 0 and 1."""
        for gate in GATES:
            assert 0.0 < gate.weight <= 1.0, f"Gate {gate.name} has invalid weight"

    def test_all_gates_have_name_and_section(self) -> None:
        """Every gate should have a name and baseline section."""
        for gate in GATES:
            assert gate.name, "Gate missing name"
            assert gate.baseline_section, f"Gate {gate.name} missing baseline_section"
            assert gate.description, f"Gate {gate.name} missing description"
