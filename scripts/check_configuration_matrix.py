#!/usr/bin/env python3
"""Configuration Adoption Matrix Checker — ADR-051 / CR-AUFG-08-09.

Validates the Configuration Adoption Matrix manifest:

    docs/architecture/governance/configuration-adoption-matrix.yaml

Enforces the ADR-051 contract:

  * every CR-08 ``expected_setting_ids`` value is classified (no drift);
  * ``user``/``project`` settings carry a ``runtime_consumer`` and
    ``enforcement_evidence`` (no exposed setting without a runtime effect);
  * ``adopted`` lifecycle entries carry ``enforcement_evidence``;
  * classifications and lifecycle values are valid;
  * no duplicate or unexpected (typo) setting_ids.

Also enforces the CR-AUFG-08-14 review-template gate: structured material
P0/P1 configuration/effect review findings must be referenced by a matrix row.

RULE-07: reads only the manifest; imports no application runtime modules.

Exit code: 0 on PASS, 1 on FAIL (blocking gate).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = str(ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from governance.configuration_matrix import (  # noqa: E402
    MatrixReport,
    MatrixStatus,
    Violation,
    load_matrix,
    parse_matrix,
    validate_matrix,
    validate_review_finding_matrix_coverage,
)
from governance.review_findings import CandidateFinding, load_findings  # noqa: E402

MATRIX_PATH = ROOT / "docs" / "architecture" / "governance" / "configuration-adoption-matrix.yaml"
CONTENT_REVIEW_DIR = ROOT / "_audit" / "results" / "content-review"
TECHNICAL_REVIEW_DIR = ROOT / "_audit" / "results" / "technical-review"


def main() -> int:
    """Run the configuration adoption matrix check and print a report."""
    try:
        data = load_matrix(MATRIX_PATH)
    except FileNotFoundError:
        print(f"FAIL: matrix file not found: {MATRIX_PATH}")
        return 1
    except Exception as exc:
        print(f"FAIL: could not parse matrix: {exc}")
        return 1

    entries, expected_ids = parse_matrix(data)
    matrix_report = validate_matrix(entries, expected_ids)
    review_report = validate_review_finding_matrix_coverage(_load_review_findings(), entries)
    report = _merge_reports(matrix_report, review_report)

    print("Configuration Adoption Matrix Check — ADR-051 / CR-AUFG-08-09")
    print("=" * 64)
    print(f"Expected setting_ids: {report.expected_count}")
    print(f"Matrix entries:       {report.total_entries}")
    print(f"Material review findings checked: {review_report.expected_count}")
    print(f"Violations:           {len(report.violations)}")
    print(f"Overall status:       {report.status.value}")
    print("-" * 64)

    if report.violations:
        grouped = _group_by_rule(report.violations)
        for rule, viols in grouped.items():
            print(f"[{rule}] ({len(viols)})")
            for v in viols:
                print(f"  - {v.setting_id}: {v.message}")
            print("-" * 64)

    return 0 if report.status == MatrixStatus.PASS else 1


def _load_review_findings(
    *,
    content_review: Path = CONTENT_REVIEW_DIR,
    technical_review: Path = TECHNICAL_REVIEW_DIR,
) -> list[CandidateFinding]:
    """Load governance findings from review artifacts covered by this gate."""
    return [
        *load_findings(content_review, pattern="cr-*.md"),
        *load_findings(technical_review),
    ]


def _group_by_rule(violations: tuple[Violation, ...]) -> dict[str, list[Violation]]:
    """Group violations by rule for readable output."""
    grouped: dict[str, list[Violation]] = {}
    for v in violations:
        grouped.setdefault(v.rule, []).append(v)
    return grouped


def _merge_reports(matrix_report: MatrixReport, review_report: MatrixReport) -> MatrixReport:
    """Merge matrix-contract and review-finding reports into one blocking verdict."""
    violations = (*matrix_report.violations, *review_report.violations)
    status = MatrixStatus.PASS if not violations else MatrixStatus.FAIL
    return MatrixReport(
        status=status,
        total_entries=matrix_report.total_entries,
        expected_count=matrix_report.expected_count,
        violations=violations,
    )


if __name__ == "__main__":
    raise SystemExit(main())
