"""Governance health aggregator (ADR-047 Phase 2).

Single responsibility (RULE-06): match candidate findings against AUFG
registry entries and produce a status-bearing health report.

This module reads the *outputs* of the registry parser and the finding
extractor. It does NOT duplicate their parsing logic (RULE-07) and does
NOT import application runtime internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from governance.aufg_registry import AufgRegistry
    from governance.review_findings import CandidateFinding

#: Lifecycle statuses that indicate a finding is actively tracked.
_TRACKED_STATUSES: frozenset[str] = frozenset(
    {
        "open",
        "in_progress",
        "blocked",
        "resolved",
        "not_applicable",
        "covered_by_existing_aufg",
    }
)

#: Lifecycle statuses that represent knowingly accepted debt.
_DEBT_STATUSES: frozenset[str] = frozenset(
    {
        "accepted_risk",
        "accepted_enhancement",
    }
)


class CoverageStatus(StrEnum):
    """Per-finding coverage classification."""

    COVERED = "covered"
    GOVERNED_DEBT = "governed_debt"
    UNMATCHED = "unmatched"


class HealthStatus(StrEnum):
    """Overall governance health verdict."""

    PASS = "PASS"  # nosec
    GOVERNED_DEBT = "GOVERNED_DEBT"
    FAIL = "FAIL"


@dataclass(frozen=True)
class FindingCoverage:
    """The coverage classification for a single candidate finding."""

    finding: CandidateFinding
    coverage: CoverageStatus
    matched_ids: tuple[str, ...]


@dataclass(frozen=True)
class GovernanceHealthReport:
    """Aggregated governance health report."""

    status: HealthStatus
    coverages: tuple[FindingCoverage, ...]
    total: int
    covered: int
    governed_debt: int
    unmatched: int


def classify_finding(
    finding: CandidateFinding,
    registry: AufgRegistry,
) -> FindingCoverage:
    """Classify a single finding against the registry.

    - No references → :attr:`CoverageStatus.UNMATCHED`.
    - References exist but none are in the registry → UNMATCHED.
    - At least one matched reference → COVERED or GOVERNED_DEBT.
    """
    if not finding.references:
        return FindingCoverage(
            finding=finding,
            coverage=CoverageStatus.UNMATCHED,
            matched_ids=(),
        )

    matched: list[str] = []
    has_debt = False

    for ref in finding.references:
        entry = registry.get(ref)
        if entry is None:
            continue
        matched.append(ref)
        if entry.status in _DEBT_STATUSES:
            has_debt = True

    if not matched:
        return FindingCoverage(
            finding=finding,
            coverage=CoverageStatus.UNMATCHED,
            matched_ids=(),
        )

    coverage = CoverageStatus.GOVERNED_DEBT if has_debt else CoverageStatus.COVERED
    return FindingCoverage(
        finding=finding,
        coverage=coverage,
        matched_ids=tuple(matched),
    )


def assess_health(
    findings: list[CandidateFinding],
    registry: AufgRegistry,
) -> GovernanceHealthReport:
    """Assess overall governance health from findings and registry."""
    coverages = tuple(classify_finding(f, registry) for f in findings)

    covered_count = sum(1 for c in coverages if c.coverage == CoverageStatus.COVERED)
    debt_count = sum(1 for c in coverages if c.coverage == CoverageStatus.GOVERNED_DEBT)
    unmatched_count = sum(1 for c in coverages if c.coverage == CoverageStatus.UNMATCHED)

    if unmatched_count > 0:
        status = HealthStatus.FAIL
    elif debt_count > 0:
        status = HealthStatus.GOVERNED_DEBT
    else:
        status = HealthStatus.PASS

    return GovernanceHealthReport(
        status=status,
        coverages=coverages,
        total=len(coverages),
        covered=covered_count,
        governed_debt=debt_count,
        unmatched=unmatched_count,
    )
