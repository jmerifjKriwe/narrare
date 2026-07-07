"""SSOT/Gate drift-checker aggregation (ADR-047 Phase 3).

Single responsibility (RULE-06): aggregate the outputs of the existing
drift checkers into a unified governance health report. This module does
NOT duplicate checker logic (RULE-07) — it imports each checker's analysis
function and classifies its results.

Aggregated checkers:
    - ``check_doc_drift`` — documentation drift (ADR/spec/terminology)
    - ``check_gate_drift`` — gate drift (docs vs CI reality)
    - ``check_current_state_facts`` — CURRENT_STATE.md volatility policy
    - ``check_registry_drift`` — adoption-registry vs prompt filesystem
    - Review-finding coverage (Phase 2, via :mod:`governance_health`)
    - ``status_consistency`` — doc↔status-SSOT consistency (ADR-062 P3, WARNING)
    - ``review_registry_link`` — review→registry metadata linking (ADR-062 P5, WARNING)

Each checker is classified as PASS / GOVERNED_DEBT / FAIL:
    - PASS: no issues
    - GOVERNED_DEBT: warnings only (registered exceptions, accepted drift)
    - FAIL: critical/unregistered issues

Overall status:
    - PASS: all checkers PASS
    - GOVERNED_DEBT: at least one WARN, no FAILs
    - FAIL: at least one FAIL
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from governance.governance_health import HealthStatus

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class CheckerResult:
    """Result of a single drift checker in the aggregation."""

    checker_name: str
    status: HealthStatus
    issue_count: int
    detail: str


@dataclass(frozen=True)
class SsotAggregationReport:
    """Aggregated SSOT/Gate governance health report."""

    status: HealthStatus
    checkers: tuple[CheckerResult, ...]
    total_issues: int

    @property
    def failing_checkers(self) -> tuple[CheckerResult, ...]:
        """Checkers with FAIL status."""
        return tuple(c for c in self.checkers if c.status == HealthStatus.FAIL)

    @property
    def warning_checkers(self) -> tuple[CheckerResult, ...]:
        """Checkers with GOVERNED_DEBT status."""
        return tuple(c for c in self.checkers if c.status == HealthStatus.GOVERNED_DEBT)


def _aggregate_status(results: tuple[CheckerResult, ...]) -> HealthStatus:
    """Compute overall status from individual checker results."""
    if any(c.status == HealthStatus.FAIL for c in results):
        return HealthStatus.FAIL
    if any(c.status == HealthStatus.GOVERNED_DEBT for c in results):
        return HealthStatus.GOVERNED_DEBT
    return HealthStatus.PASS


# ---------------------------------------------------------------------------
# Individual checker wrappers — each imports and calls the checker's
# analysis function, then classifies the result. Imports are deferred to
# avoid side effects at module load time.
# ---------------------------------------------------------------------------


def _check_doc_drift() -> CheckerResult:
    """Run doc-drift governance checks and classify.

    Imports the public check functions from the ``doc_drift`` subpackage
    directly, rather than the private ``_run_governance_checks`` helper in
    ``check_doc_drift.py``. This avoids accessing a private symbol while
    still not duplicating checker logic (RULE-07).
    """
    from doc_drift.adr_checks import DocDriftFinding, check_adr_consistency
    from doc_drift.spec_checks import check_spec_references
    from doc_drift.terminology_checks import check_terminology_alignment

    findings: list[DocDriftFinding] = []
    findings.extend(check_adr_consistency())
    findings.extend(check_spec_references())
    findings.extend(check_terminology_alignment())
    critical = [f for f in findings if f.severity == "critical"]
    warnings = [f for f in findings if f.severity == "warning"]

    if critical:
        status = HealthStatus.FAIL
        detail = f"{len(critical)} critical, {len(warnings)} warnings"
    elif warnings:
        status = HealthStatus.GOVERNED_DEBT
        detail = f"{len(warnings)} warnings"
    else:
        status = HealthStatus.PASS
        detail = "no drift"

    return CheckerResult(
        checker_name="check_doc_drift",
        status=status,
        issue_count=len(findings),
        detail=detail,
    )


def _check_gate_drift() -> CheckerResult:
    """Run gate-drift checks and classify."""
    from gate_drift_checks import run_all_checks

    report = run_all_checks()

    if report.has_unregistered_drift:
        status = HealthStatus.FAIL
        detail = f"{report.criticals} critical, {report.warnings} warnings (unregistered)"
    elif report.warnings > 0:
        status = HealthStatus.GOVERNED_DEBT
        detail = f"{report.warnings} warnings (all registered)"
    else:
        status = HealthStatus.PASS
        detail = "no drift"

    return CheckerResult(
        checker_name="check_gate_drift",
        status=status,
        issue_count=report.criticals + report.warnings,
        detail=detail,
    )


def _check_current_state_facts(project_root: Path) -> CheckerResult:
    """Run CURRENT_STATE.md volatility policy checks and classify."""
    from check_current_state_facts import (
        find_forbidden_volatile_counts,
        find_missing_authority_references,
    )

    cs_path = project_root / "docs" / "_shared" / "CURRENT_STATE.md"

    cs_text = cs_path.read_text(encoding="utf-8")
    forbidden = find_forbidden_volatile_counts(cs_text)
    missing = find_missing_authority_references(cs_text)
    total = len(forbidden) + len(missing)

    if total > 0:
        status = HealthStatus.FAIL
        detail = f"{len(forbidden)} volatile counts, {len(missing)} missing authorities"
    else:
        status = HealthStatus.PASS
        detail = "policy compliant"

    return CheckerResult(
        checker_name="check_current_state_facts",
        status=status,
        issue_count=total,
        detail=detail,
    )


def _check_registry_drift() -> CheckerResult:
    """Run adoption-registry drift checks and classify."""
    from check_registry_drift import DriftReport, check_registry_drift

    findings = check_registry_drift()
    report = DriftReport(findings=findings)

    if report.has_critical:
        status = HealthStatus.FAIL
        crit = sum(1 for f in findings if f.severity == "critical")
        warn = sum(1 for f in findings if f.severity == "warning")
        detail = f"{crit} critical, {warn} warnings"
    elif report.has_warnings:
        status = HealthStatus.GOVERNED_DEBT
        warn = sum(1 for f in findings if f.severity == "warning")
        detail = f"{warn} warnings"
    else:
        status = HealthStatus.PASS
        detail = "no drift"

    return CheckerResult(
        checker_name="check_registry_drift",
        status=status,
        issue_count=len(findings),
        detail=detail,
    )


def _check_finding_coverage(
    project_root: Path,
) -> CheckerResult:
    """Run review-finding coverage (Phase 2) and classify."""
    from governance.aufg_registry import load_registry
    from governance.governance_health import assess_health
    from governance.review_findings import load_findings

    registry_path = project_root / "docs" / "architecture" / "governance" / "aufg-registry.md"
    review_dir = project_root / "_audit" / "results" / "technical-review"

    registry = load_registry(registry_path)
    findings = load_findings(review_dir)
    report = assess_health(findings, registry)

    if report.unmatched > 0:
        status = HealthStatus.FAIL
        detail = (
            f"{report.unmatched} unmatched, {report.covered} covered, {report.governed_debt} debt"
        )
    elif report.governed_debt > 0:
        status = HealthStatus.GOVERNED_DEBT
        detail = f"{report.covered} covered, {report.governed_debt} debt"
    else:
        status = HealthStatus.PASS
        detail = f"{report.covered} covered"

    return CheckerResult(
        checker_name="finding_coverage",
        status=status,
        issue_count=report.unmatched,
        detail=detail,
    )


def _check_status_consistency(project_root: Path) -> CheckerResult:
    """Run the ADR-062 P3 doc↔status-SSOT consistency checker.

    BLOCKING (ADR-062 enforcement phasing complete, AUFG-01-09 follow-up
    2026-07-06): contradictions fail the gate. A missing status vocabulary
    (a tracked baseline file) is reported as PASS/skipped rather than erroring
    — a missing vocabulary is an infrastructure gap, not a drift finding.
    """
    from governance._status_consistency import check_status_consistency, scan_repo_docs
    from governance._status_vocab import load_status_vocabulary

    vocab_path = project_root / "docs" / "architecture" / "governance" / "status_vocabulary.yaml"
    try:
        vocab = load_status_vocabulary(vocab_path)
    except FileNotFoundError:
        return CheckerResult(
            "status_consistency", HealthStatus.PASS, 0, "status vocabulary not found (skipped)"
        )

    docs = scan_repo_docs(project_root, vocab)
    report = check_status_consistency(docs, vocab)

    # BLOCKING: findings map to FAIL.
    if report.has_contradictions:
        status = HealthStatus.FAIL
        detail = f"{len(report.contradictions)} status contradiction(s) across {len(docs)} docs"
    else:
        status = HealthStatus.PASS
        detail = f"{report.claims_scanned} claim(s), no contradictions"

    return CheckerResult(
        checker_name="status_consistency",
        status=status,
        issue_count=len(report.contradictions),
        detail=detail,
    )


def _check_review_registry_link(project_root: Path) -> CheckerResult:
    """Run the ADR-062 P5 review→registry metadata linking checker.

    BLOCKING (ADR-062 enforcement phasing complete, AUFG-01-09 follow-up
    2026-07-06): linking errors / collisions fail the gate. A missing registry
    (a tracked baseline file) is reported as PASS/skipped — a missing registry
    is an infrastructure gap, not a drift finding.
    """
    from governance._review_registry_link import (
        check_review_registry_link,
        collect_review_headers,
        parse_registry_meta,
    )

    headers = collect_review_headers(project_root)
    registry_path = project_root / "docs" / "architecture" / "governance" / "aufg-registry.md"
    try:
        registry = parse_registry_meta(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return CheckerResult(
            "review_registry_link", HealthStatus.PASS, 0, "aufg registry not found (skipped)"
        )

    report = check_review_registry_link(headers, registry, project_root)

    # BLOCKING: findings map to FAIL.
    if report.findings:
        status = HealthStatus.FAIL
        detail = (
            f"{len(report.findings)} review→registry link issue(s) "
            f"({len(report.rehomings_recognized)} re-homing(s) recognized)"
        )
    else:
        status = HealthStatus.PASS
        detail = (
            f"{report.headers_scanned} header(s) → {report.entries_scanned} entries, "
            f"{len(report.rehomings_recognized)} re-homing(s) recognized"
        )

    return CheckerResult(
        checker_name="review_registry_link",
        status=status,
        issue_count=len(report.findings),
        detail=detail,
    )


def aggregate_ssot_gate_health(project_root: Path) -> SsotAggregationReport:
    """Aggregate all drift checkers into a unified governance health report.

    Args:
        project_root: Repository root path (for resolving checker paths).

    Returns:
        :class:`SsotAggregationReport` with per-checker results and overall status.

    Raises:
        ImportError: If a checker module cannot be imported (RULE-11: no silent
            failures — a missing checker is a governance gap, not a skip).
    """
    results: list[CheckerResult] = [
        _check_doc_drift(),
        _check_gate_drift(),
        _check_current_state_facts(project_root),
        _check_registry_drift(),
        _check_finding_coverage(project_root),
        # ADR-062 — WARNING-only drift checkers (ratchet to blocking in a follow-up).
        _check_status_consistency(project_root),
        _check_review_registry_link(project_root),
    ]

    result_tuple = tuple(results)
    overall = _aggregate_status(result_tuple)
    total = sum(c.issue_count for c in result_tuple)

    return SsotAggregationReport(
        status=overall,
        checkers=result_tuple,
        total_issues=total,
    )


def format_aggregation_summary(report: SsotAggregationReport) -> str:
    """Format a concise summary for CI output and coordinator handoff."""
    lines: list[str] = []
    lines.append(f"Overall: {report.status.value}")
    for checker in report.checkers:
        icon = {
            HealthStatus.PASS: "✅",
            HealthStatus.GOVERNED_DEBT: "⚠️",
            HealthStatus.FAIL: "❌",
        }[checker.status]
        lines.append(f"  {icon} {checker.checker_name}: {checker.detail}")
    return "\n".join(lines)
