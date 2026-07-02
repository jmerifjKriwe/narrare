"""Tests for SSOT/Gate drift-checker aggregation (ADR-047 Phase 3).

Tests that the aggregation module correctly classifies each checker's
output and produces the right overall PASS/GOVERNED_DEBT/FAIL status.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance.governance_health import HealthStatus  # noqa: E402
from governance.ssot_aggregation import (  # noqa: E402
    CheckerResult,
    SsotAggregationReport,
    _aggregate_status,
    format_aggregation_summary,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    name: str,
    status: HealthStatus,
    issues: int = 0,
    detail: str = "",
) -> CheckerResult:
    return CheckerResult(
        checker_name=name,
        status=status,
        issue_count=issues,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# _aggregate_status
# ---------------------------------------------------------------------------


def test_aggregate_status_all_pass_is_pass() -> None:
    """All checkers PASS → overall PASS."""
    results = (
        _make_result("a", HealthStatus.PASS),
        _make_result("b", HealthStatus.PASS),
    )
    assert _aggregate_status(results) == HealthStatus.PASS


def test_aggregate_status_one_warn_no_fail_is_governed_debt() -> None:
    """One WARN, no FAIL → GOVERNED_DEBT."""
    results = (
        _make_result("a", HealthStatus.PASS),
        _make_result("b", HealthStatus.GOVERNED_DEBT),
    )
    assert _aggregate_status(results) == HealthStatus.GOVERNED_DEBT


def test_aggregate_status_one_fail_is_fail() -> None:
    """Any FAIL → overall FAIL."""
    results = (
        _make_result("a", HealthStatus.PASS),
        _make_result("b", HealthStatus.FAIL),
    )
    assert _aggregate_status(results) == HealthStatus.FAIL


def test_aggregate_status_warn_and_fail_is_fail() -> None:
    """FAIL takes priority over WARN."""
    results = (
        _make_result("a", HealthStatus.GOVERNED_DEBT),
        _make_result("b", HealthStatus.FAIL),
    )
    assert _aggregate_status(results) == HealthStatus.FAIL


def test_aggregate_status_empty_is_pass() -> None:
    """No checkers → PASS."""
    assert _aggregate_status(()) == HealthStatus.PASS


# ---------------------------------------------------------------------------
# SsotAggregationReport properties
# ---------------------------------------------------------------------------


def test_report_failing_checkers_filters_fail() -> None:
    """failing_checkers returns only FAIL results."""
    report = SsotAggregationReport(
        status=HealthStatus.FAIL,
        checkers=(
            _make_result("a", HealthStatus.PASS),
            _make_result("b", HealthStatus.FAIL),
            _make_result("c", HealthStatus.GOVERNED_DEBT),
        ),
        total_issues=5,
    )
    assert len(report.failing_checkers) == 1
    assert report.failing_checkers[0].checker_name == "b"


def test_report_warning_checkers_filters_debt() -> None:
    """warning_checkers returns only GOVERNED_DEBT results."""
    report = SsotAggregationReport(
        status=HealthStatus.GOVERNED_DEBT,
        checkers=(
            _make_result("a", HealthStatus.PASS),
            _make_result("b", HealthStatus.GOVERNED_DEBT),
        ),
        total_issues=3,
    )
    assert len(report.warning_checkers) == 1
    assert report.warning_checkers[0].checker_name == "b"


# ---------------------------------------------------------------------------
# format_aggregation_summary
# ---------------------------------------------------------------------------


def test_format_summary_includes_all_checkers() -> None:
    """Summary includes each checker with its status icon."""
    report = SsotAggregationReport(
        status=HealthStatus.GOVERNED_DEBT,
        checkers=(
            _make_result("checker_a", HealthStatus.PASS, detail="ok"),
            _make_result("checker_b", HealthStatus.GOVERNED_DEBT, detail="1 warn"),
        ),
        total_issues=1,
    )
    summary = format_aggregation_summary(report)
    assert "GOVERNED_DEBT" in summary
    assert "checker_a" in summary
    assert "checker_b" in summary
    assert "✅" in summary
    assert "⚠️" in summary


def test_format_summary_fail_includes_cross() -> None:
    """Summary for FAIL includes ❌ icon."""
    report = SsotAggregationReport(
        status=HealthStatus.FAIL,
        checkers=(_make_result("bad_checker", HealthStatus.FAIL, detail="broken"),),
        total_issues=1,
    )
    summary = format_aggregation_summary(report)
    assert "❌" in summary
    assert "FAIL" in summary


# ---------------------------------------------------------------------------
# Integration: aggregate_ssot_gate_health with mocked checkers
# ---------------------------------------------------------------------------


def test_aggregate_all_pass_with_mocks(tmp_path: Path) -> None:
    """Full aggregation with all checkers mocked to PASS → PASS."""
    with (
        patch("governance.ssot_aggregation._check_doc_drift") as mock_doc,
        patch("governance.ssot_aggregation._check_gate_drift") as mock_gate,
        patch("governance.ssot_aggregation._check_current_state_facts") as mock_csf,
        patch("governance.ssot_aggregation._check_registry_drift") as mock_reg,
        patch("governance.ssot_aggregation._check_finding_coverage") as mock_fc,
        patch("governance.ssot_aggregation._check_status_consistency") as mock_sc,
        patch("governance.ssot_aggregation._check_review_registry_link") as mock_rr,
    ):
        mock_doc.return_value = _make_result("check_doc_drift", HealthStatus.PASS)
        mock_gate.return_value = _make_result("check_gate_drift", HealthStatus.PASS)
        mock_csf.return_value = _make_result("check_current_state_facts", HealthStatus.PASS)
        mock_reg.return_value = _make_result("check_registry_drift", HealthStatus.PASS)
        mock_fc.return_value = _make_result("finding_coverage", HealthStatus.PASS)
        mock_sc.return_value = _make_result("status_consistency", HealthStatus.PASS)
        mock_rr.return_value = _make_result("review_registry_link", HealthStatus.PASS)

        from governance.ssot_aggregation import aggregate_ssot_gate_health

        report = aggregate_ssot_gate_health(tmp_path)

    assert report.status == HealthStatus.PASS
    assert len(report.checkers) == 7
    assert report.total_issues == 0


def test_aggregate_one_warn_with_mocks(tmp_path: Path) -> None:
    """One checker GOVERNED_DEBT, rest PASS → GOVERNED_DEBT."""
    with (
        patch("governance.ssot_aggregation._check_doc_drift") as mock_doc,
        patch("governance.ssot_aggregation._check_gate_drift") as mock_gate,
        patch("governance.ssot_aggregation._check_current_state_facts") as mock_csf,
        patch("governance.ssot_aggregation._check_registry_drift") as mock_reg,
        patch("governance.ssot_aggregation._check_finding_coverage") as mock_fc,
        patch("governance.ssot_aggregation._check_status_consistency") as mock_sc,
        patch("governance.ssot_aggregation._check_review_registry_link") as mock_rr,
    ):
        mock_doc.return_value = _make_result(
            "check_doc_drift", HealthStatus.GOVERNED_DEBT, issues=5, detail="5 warnings"
        )
        mock_gate.return_value = _make_result("check_gate_drift", HealthStatus.PASS)
        mock_csf.return_value = _make_result("check_current_state_facts", HealthStatus.PASS)
        mock_reg.return_value = _make_result("check_registry_drift", HealthStatus.PASS)
        mock_fc.return_value = _make_result("finding_coverage", HealthStatus.PASS)
        mock_sc.return_value = _make_result("status_consistency", HealthStatus.PASS)
        mock_rr.return_value = _make_result("review_registry_link", HealthStatus.PASS)

        from governance.ssot_aggregation import aggregate_ssot_gate_health

        report = aggregate_ssot_gate_health(tmp_path)

    assert report.status == HealthStatus.GOVERNED_DEBT
    assert report.total_issues == 5


def test_aggregate_one_fail_with_mocks(tmp_path: Path) -> None:
    """One checker FAIL → overall FAIL."""
    with (
        patch("governance.ssot_aggregation._check_doc_drift") as mock_doc,
        patch("governance.ssot_aggregation._check_gate_drift") as mock_gate,
        patch("governance.ssot_aggregation._check_current_state_facts") as mock_csf,
        patch("governance.ssot_aggregation._check_registry_drift") as mock_reg,
        patch("governance.ssot_aggregation._check_finding_coverage") as mock_fc,
        patch("governance.ssot_aggregation._check_status_consistency") as mock_sc,
        patch("governance.ssot_aggregation._check_review_registry_link") as mock_rr,
    ):
        mock_doc.return_value = _make_result("check_doc_drift", HealthStatus.PASS)
        mock_gate.return_value = _make_result("check_gate_drift", HealthStatus.PASS)
        mock_csf.return_value = _make_result(
            "check_current_state_facts", HealthStatus.FAIL, issues=2, detail="2 violations"
        )
        mock_reg.return_value = _make_result("check_registry_drift", HealthStatus.PASS)
        mock_fc.return_value = _make_result("finding_coverage", HealthStatus.PASS)
        mock_sc.return_value = _make_result("status_consistency", HealthStatus.PASS)
        mock_rr.return_value = _make_result("review_registry_link", HealthStatus.PASS)

        from governance.ssot_aggregation import aggregate_ssot_gate_health

        report = aggregate_ssot_gate_health(tmp_path)

    assert report.status == HealthStatus.FAIL
    assert len(report.failing_checkers) == 1
    assert report.failing_checkers[0].checker_name == "check_current_state_facts"


# ---------------------------------------------------------------------------
# ADR-062 — P3/P5 are WARNING-only: findings → GOVERNED_DEBT, never FAIL.
# ---------------------------------------------------------------------------


def test_aggregate_adr062_warning_checkers_never_fail_gate(tmp_path: Path) -> None:
    """Both ADR-062 drift checkers reporting findings → GOVERNED_DEBT, not FAIL.

    The P3/P5 checkers ship WARNING-only (ADR-062 enforcement phasing): even
    when they find contradictions / linking errors, the overall gate must stay
    GOVERNED_DEBT (tracked debt), never FAIL — so they cannot break CI green.
    """
    with (
        patch("governance.ssot_aggregation._check_doc_drift") as mock_doc,
        patch("governance.ssot_aggregation._check_gate_drift") as mock_gate,
        patch("governance.ssot_aggregation._check_current_state_facts") as mock_csf,
        patch("governance.ssot_aggregation._check_registry_drift") as mock_reg,
        patch("governance.ssot_aggregation._check_finding_coverage") as mock_fc,
        patch("governance.ssot_aggregation._check_status_consistency") as mock_sc,
        patch("governance.ssot_aggregation._check_review_registry_link") as mock_rr,
    ):
        mock_doc.return_value = _make_result("check_doc_drift", HealthStatus.PASS)
        mock_gate.return_value = _make_result("check_gate_drift", HealthStatus.PASS)
        mock_csf.return_value = _make_result("check_current_state_facts", HealthStatus.PASS)
        mock_reg.return_value = _make_result("check_registry_drift", HealthStatus.PASS)
        mock_fc.return_value = _make_result("finding_coverage", HealthStatus.PASS)
        mock_sc.return_value = _make_result(
            "status_consistency", HealthStatus.GOVERNED_DEBT, issues=3, detail="3 contradictions"
        )
        mock_rr.return_value = _make_result(
            "review_registry_link", HealthStatus.GOVERNED_DEBT, issues=2, detail="2 link findings"
        )

        from governance.ssot_aggregation import aggregate_ssot_gate_health

        report = aggregate_ssot_gate_health(tmp_path)

    assert report.status == HealthStatus.GOVERNED_DEBT
    assert report.status != HealthStatus.FAIL
    assert {c.checker_name for c in report.warning_checkers} == {
        "status_consistency",
        "review_registry_link",
    }


def test_status_consistency_wrapper_maps_findings_to_governed_debt(tmp_path: Path) -> None:
    """The P3 wrapper classifies contradictions as GOVERNED_DEBT, never FAIL."""
    from governance._status_consistency import StatusConsistencyReport
    from governance.ssot_aggregation import _check_status_consistency

    fake = StatusConsistencyReport(contradictions=("x", "y", "z"), claims_scanned=5)  # type: ignore[arg-type]

    with (
        patch("governance._status_consistency.scan_repo_docs", return_value={}),
        patch("governance._status_consistency.check_status_consistency", return_value=fake),
        patch("governance._status_vocab.load_status_vocabulary"),
    ):
        result = _check_status_consistency(tmp_path)

    assert result.checker_name == "status_consistency"
    assert result.status == HealthStatus.GOVERNED_DEBT
    assert result.status != HealthStatus.FAIL
    assert result.issue_count == 3


def test_review_registry_link_wrapper_maps_findings_to_governed_debt(tmp_path: Path) -> None:
    """The P5 wrapper classifies link findings as GOVERNED_DEBT, never FAIL."""
    from governance._review_registry_link import ReviewLinkReport
    from governance.ssot_aggregation import _check_review_registry_link

    # The wrapper reads the registry file; provide a minimal one so parsing runs.
    reg = tmp_path / "docs" / "architecture" / "governance" / "aufg-registry.md"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text("### AUFG-01-01 — Title\n\n| Source | review-x.md |\n\n", encoding="utf-8")

    fake = ReviewLinkReport(findings=("a", "b"), headers_scanned=4, entries_scanned=10)  # type: ignore[arg-type]

    with (
        patch("governance._review_registry_link.collect_review_headers", return_value=[]),
        patch("governance._review_registry_link.check_review_registry_link", return_value=fake),
    ):
        result = _check_review_registry_link(tmp_path)

    assert result.checker_name == "review_registry_link"
    assert result.status == HealthStatus.GOVERNED_DEBT
    assert result.status != HealthStatus.FAIL
    assert result.issue_count == 2
