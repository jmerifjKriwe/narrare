"""Tests for the CR-AUFG-08-14 matrix review-finding prevention gate."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_configuration_matrix import _load_review_findings  # noqa: E402
from governance.configuration_matrix import (  # noqa: E402
    MatrixEntry,
    MatrixReport,
    MatrixStatus,
    validate_review_finding_matrix_coverage,
)
from governance.review_findings import CandidateFinding  # noqa: E402


def _entry(
    setting_id: str,
    *,
    cr_task: str | None = None,
    finding: str | None = None,
) -> MatrixEntry:
    """Build a matrix entry for review-gate tests."""
    return MatrixEntry(
        setting_id=setting_id,
        classification="operator",
        lifecycle="formal_finding",
        source="code default",
        resolver_service="Service.resolve",
        effect_semantics="changes X",
        fallback_policy="warning",
        cr_task=cr_task,
        finding=finding,
    )


def _finding(
    text: str,
    *,
    source_file: str = "review-cr-08.md",
    line_number: int = 12,
) -> CandidateFinding:
    """Build a structured review finding for matrix-gate tests."""
    return CandidateFinding(
        source_file=source_file,
        line_number=line_number,
        text=text,
        references=(),
    )


def _rules(report: MatrixReport) -> set[str]:
    """Return the set of violated rule names."""
    return {v.rule for v in report.violations}


def test_material_p1_review_finding_without_matrix_reference_fails() -> None:
    """A structured P1 config/effect finding must be classified in the matrix."""
    entries = [_entry("known", cr_task="CR-AUFG-08-01", finding="FIND-001")]
    findings = [
        _finding(
            "[P1] [category: configuration-effect] FIND-099 / CR-AUFG-08-99 "
            "hardcoded model cap changes runtime effect without matrix classification."
        )
    ]

    report = validate_review_finding_matrix_coverage(findings, entries)

    assert report.status == MatrixStatus.FAIL
    assert "unclassified_material_review_finding" in _rules(report)
    assert "CR-AUFG-08-99" in report.violations[0].message
    assert "configuration-adoption-matrix.yaml" in report.violations[0].message


def test_material_p1_review_finding_with_matrix_reference_passes() -> None:
    """A material P1 finding is governed when a matrix entry references it."""
    entries = [
        _entry(
            "classified_runtime_cap",
            cr_task="CR-AUFG-08-99",
            finding="FIND-099",
        )
    ]
    findings = [
        _finding(
            "[P1] [category: configuration-effect] FIND-099 / CR-AUFG-08-99 "
            "hardcoded model cap changes runtime effect."
        )
    ]

    report = validate_review_finding_matrix_coverage(findings, entries)

    assert report.status == MatrixStatus.PASS
    assert report.violations == ()


def test_p2_review_finding_without_matrix_reference_is_not_part_of_minimum_gate() -> None:
    """The prevention gate baseline is P0/P1 material findings."""
    findings = [
        _finding(
            "[P2] [category: configuration-effect] FIND-099 / CR-AUFG-08-99 "
            "operator default needs later classification."
        )
    ]

    report = validate_review_finding_matrix_coverage(findings, [])

    assert report.status == MatrixStatus.PASS
    assert report.violations == ()


def test_review_finding_loader_includes_future_content_reviews(tmp_path: Path) -> None:
    """The wired checker must scan future content reviews, not only technical reviews."""
    content_review = tmp_path / "content-review"
    technical_review = tmp_path / "technical-review"
    content_review.mkdir()
    technical_review.mkdir()
    (content_review / "cr-99-new-review.md").write_text(
        "### Offene Punkte\n"
        "- [P1] [category: configuration-effect] FIND-099 / CR-AUFG-08-99 "
        "new material value needs matrix classification.\n",
        encoding="utf-8",
    )
    (technical_review / "review-99.md").write_text(
        "### Offene Punkte\n- [P2] General non-blocking technical review finding.\n",
        encoding="utf-8",
    )

    findings = _load_review_findings(
        content_review=content_review, technical_review=technical_review
    )

    assert {finding.source_file for finding in findings} == {
        "cr-99-new-review.md",
        "review-99.md",
    }
