"""Tests for the governance health aggregator (ADR-047 Phase 2).

Tests the matching logic between candidate findings and AUFG registry
lifecycle entries, producing PASS / GOVERNED_DEBT / FAIL status.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance.aufg_registry import AufgEntry, AufgRegistry  # noqa: E402
from governance.governance_health import (  # noqa: E402
    CoverageStatus,
    GovernanceHealthReport,
    HealthStatus,
    assess_health,
    classify_finding,
)
from governance.review_findings import CandidateFinding  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(entry_id: str, status: str) -> AufgEntry:
    return AufgEntry(entry_id=entry_id, title=f"Entry {entry_id}", status=status)


def _make_registry(*entries: AufgEntry) -> AufgRegistry:
    return AufgRegistry(entries={e.entry_id: e for e in entries})


def _make_finding(
    text: str = "some finding",
    references: tuple[str, ...] = (),
    line: int = 1,
) -> CandidateFinding:
    return CandidateFinding(
        source_file="review.md",
        line_number=line,
        text=text,
        references=references,
    )


# ---------------------------------------------------------------------------
# classify_finding
# ---------------------------------------------------------------------------


def test_classify_finding_no_references_is_unmatched() -> None:
    """A finding with zero references is UNMATCHED."""
    registry = _make_registry(_make_entry("AUFG-05-07", "resolved"))
    finding = _make_finding("prose-only risk", references=())

    result = classify_finding(finding, registry)

    assert result.coverage == CoverageStatus.UNMATCHED


def test_classify_finding_matched_to_resolved_aufg_is_covered() -> None:
    """A finding referencing a resolved AUFG is COVERED."""
    registry = _make_registry(_make_entry("AUFG-05-07", "resolved"))
    finding = _make_finding("CORS audit", references=("AUFG-05-07",))

    result = classify_finding(finding, registry)

    assert result.coverage == CoverageStatus.COVERED
    assert "AUFG-05-07" in result.matched_ids


def test_classify_finding_matched_to_open_aufg_is_covered() -> None:
    """A finding referencing an open AUFG is COVERED (lifecycle tracked)."""
    registry = _make_registry(_make_entry("AUFG-05-12", "open"))
    finding = _make_finding("rate limiting", references=("AUFG-05-12",))

    result = classify_finding(finding, registry)

    assert result.coverage == CoverageStatus.COVERED


def test_classify_finding_matched_to_accepted_risk_is_governed_debt() -> None:
    """A finding referencing an accepted risk is GOVERNED_DEBT."""
    registry = _make_registry(_make_entry("AR-05-02", "accepted_risk"))
    finding = _make_finding("in-memory rate limit", references=("AR-05-02",))

    result = classify_finding(finding, registry)

    assert result.coverage == CoverageStatus.GOVERNED_DEBT


def test_classify_finding_matched_to_accepted_enhancement_is_governed_debt() -> None:
    """A finding referencing an accepted enhancement is GOVERNED_DEBT."""
    registry = _make_registry(_make_entry("AE-05-01", "accepted_enhancement"))
    finding = _make_finding("cosign signing", references=("AE-05-01",))

    result = classify_finding(finding, registry)

    assert result.coverage == CoverageStatus.GOVERNED_DEBT


def test_classify_finding_reference_not_in_registry_is_unmatched() -> None:
    """A finding referencing a non-existent entry is UNMATCHED."""
    registry = _make_registry(_make_entry("AUFG-05-07", "resolved"))
    finding = _make_finding("typo ref", references=("AUFG-99-99",))

    result = classify_finding(finding, registry)

    assert result.coverage == CoverageStatus.UNMATCHED
    assert result.matched_ids == ()


def test_classify_finding_mixed_debt_and_tracked_is_governed_debt() -> None:
    """If any matched reference is debt, the finding is GOVERNED_DEBT."""
    registry = _make_registry(
        _make_entry("AUFG-05-07", "resolved"),
        _make_entry("AR-05-02", "accepted_risk"),
    )
    finding = _make_finding("mixed", references=("AUFG-05-07", "AR-05-02"))

    result = classify_finding(finding, registry)

    assert result.coverage == CoverageStatus.GOVERNED_DEBT


# ---------------------------------------------------------------------------
# assess_health — overall status
# ---------------------------------------------------------------------------


def test_assess_health_all_covered_is_pass() -> None:
    """All findings matched to resolved/open AUFGs → PASS."""
    registry = _make_registry(
        _make_entry("AUFG-05-07", "resolved"),
        _make_entry("AUFG-05-08", "resolved"),
    )
    findings = [
        _make_finding("CORS", references=("AUFG-05-07",)),
        _make_finding("CSRF", references=("AUFG-05-08",)),
    ]

    report = assess_health(findings, registry)

    assert report.status == HealthStatus.PASS
    assert report.covered == 2
    assert report.governed_debt == 0
    assert report.unmatched == 0
    assert report.total == 2


def test_assess_health_with_governed_debt_is_governed_debt() -> None:
    """All covered, but some via accepted risk → GOVERNED_DEBT."""
    registry = _make_registry(
        _make_entry("AUFG-05-07", "resolved"),
        _make_entry("AR-05-02", "accepted_risk"),
    )
    findings = [
        _make_finding("CORS", references=("AUFG-05-07",)),
        _make_finding("backend", references=("AR-05-02",)),
    ]

    report = assess_health(findings, registry)

    assert report.status == HealthStatus.GOVERNED_DEBT
    assert report.covered == 1
    assert report.governed_debt == 1
    assert report.unmatched == 0


def test_assess_health_with_unmatched_is_fail() -> None:
    """Any unmatched finding → FAIL."""
    registry = _make_registry(_make_entry("AUFG-05-07", "resolved"))
    findings = [
        _make_finding("CORS", references=("AUFG-05-07",)),
        _make_finding("prose risk", references=()),
    ]

    report = assess_health(findings, registry)

    assert report.status == HealthStatus.FAIL
    assert report.unmatched == 1


def test_assess_health_mixed_unmatched_and_debt_is_fail() -> None:
    """Unmatched takes priority over debt → FAIL."""
    registry = _make_registry(_make_entry("AR-05-02", "accepted_risk"))
    findings = [
        _make_finding("backend", references=("AR-05-02",)),
        _make_finding("prose risk", references=()),
    ]

    report = assess_health(findings, registry)

    assert report.status == HealthStatus.FAIL
    assert report.governed_debt == 1
    assert report.unmatched == 1


def test_assess_health_no_findings_is_pass() -> None:
    """Zero findings → PASS (nothing to track)."""
    registry = _make_registry(_make_entry("AUFG-05-07", "resolved"))

    report = assess_health([], registry)

    assert report.status == HealthStatus.PASS
    assert report.total == 0


def test_assess_health_report_contains_all_coverages() -> None:
    """The report coverages tuple has one entry per finding."""
    registry = _make_registry(
        _make_entry("AUFG-05-07", "resolved"),
        _make_entry("AR-05-02", "accepted_risk"),
    )
    findings = [
        _make_finding("CORS", references=("AUFG-05-07",)),
        _make_finding("backend", references=("AR-05-02",)),
        _make_finding("prose", references=()),
    ]

    report = assess_health(findings, registry)

    assert len(report.coverages) == 3
    statuses = [c.coverage for c in report.coverages]
    assert CoverageStatus.COVERED in statuses
    assert CoverageStatus.GOVERNED_DEBT in statuses
    assert CoverageStatus.UNMATCHED in statuses


# ---------------------------------------------------------------------------
# Dataclass shape
# ---------------------------------------------------------------------------


def test_health_report_is_frozen() -> None:
    """GovernanceHealthReport is immutable."""
    report = GovernanceHealthReport(
        status=HealthStatus.PASS,
        coverages=(),
        total=0,
        covered=0,
        governed_debt=0,
        unmatched=0,
    )

    assert report.status == HealthStatus.PASS
    assert report.total == 0
