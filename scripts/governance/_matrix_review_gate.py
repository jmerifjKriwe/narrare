"""Review-finding coverage gate for the Configuration Adoption Matrix.

Single responsibility (RULE-06): enforce CR-AUFG-08-14's machine-readable
template equivalent. Structured material P0/P1 configuration/effect review
findings must be represented by a Configuration Adoption Matrix entry via a
``cr_task`` or ``finding`` reference.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from governance._matrix_types import MatrixEntry, MatrixReport, MatrixStatus, Violation

if TYPE_CHECKING:
    from governance.review_findings import CandidateFinding

_MATERIAL_PRIORITIES: frozenset[str] = frozenset({"P0", "P1"})
_PRIORITY_RE = re.compile(r"(?:^|[\s\[(])(?P<priority>P[0-4])(?:$|[\s\])])", re.IGNORECASE)
_CR08_RE = re.compile(r"\bCR-AUFG-08-\d{2}\b")
_FINDING_RE = re.compile(r"\bFIND-\d{3}\b")
_CONFIG_EFFECT_RE = re.compile(
    r"(?:category\s*:\s*configuration-effect|\[configuration-effect\])",
    re.IGNORECASE,
)


def validate_review_finding_matrix_coverage(
    findings: list[CandidateFinding],
    entries: list[MatrixEntry],
) -> MatrixReport:
    """Validate material P0/P1 config/effect findings against matrix entries.

    The gate is intentionally structured: it keys off explicit review-template
    markers (priority plus ``category: configuration-effect``) and stable review
    IDs (``CR-AUFG-08-xx`` / ``FIND-xxx``), not arbitrary number or prose grep.
    """
    matrix_refs = _matrix_references(entries)
    violations = tuple(
        violation
        for finding in findings
        if _is_material_config_effect_finding(finding.text)
        for violation in _coverage_violation(finding, matrix_refs)
    )
    status = MatrixStatus.PASS if not violations else MatrixStatus.FAIL
    return MatrixReport(
        status=status,
        total_entries=len(entries),
        expected_count=sum(
            1 for finding in findings if _is_material_config_effect_finding(finding.text)
        ),
        violations=violations,
    )


def _is_material_config_effect_finding(text: str) -> bool:
    """Return True for structured P0/P1 configuration/effect review items."""
    priorities = {match.group("priority").upper() for match in _PRIORITY_RE.finditer(text)}
    return bool(priorities & _MATERIAL_PRIORITIES) and bool(_CONFIG_EFFECT_RE.search(text))


def _coverage_violation(
    finding: CandidateFinding,
    matrix_refs: frozenset[str],
) -> tuple[Violation, ...]:
    """Return a violation when a material finding is not matrix-classified."""
    refs = _finding_references(finding.text)
    if refs and refs & matrix_refs:
        return ()

    ref_text = ", ".join(sorted(refs)) if refs else "no CR-AUFG-08/FIND reference"
    location = f"{finding.source_file}:{finding.line_number}"
    return (
        Violation(
            rule="unclassified_material_review_finding",
            setting_id=location,
            message=(
                f"material P0/P1 configuration/effect review finding ({ref_text}) "
                "is not referenced by any Configuration Adoption Matrix entry; "
                "classify the material value in "
                "docs/architecture/governance/configuration-adoption-matrix.yaml "
                "with setting_id, classification/lifecycle, and cr_task/finding evidence"
            ),
        ),
    )


def _matrix_references(entries: list[MatrixEntry]) -> frozenset[str]:
    """Return all CR/FIND references already represented by matrix entries."""
    refs: set[str] = set()
    for entry in entries:
        if entry.cr_task:
            refs.add(entry.cr_task)
        if entry.finding:
            refs.add(entry.finding)
    return frozenset(refs)


def _finding_references(text: str) -> frozenset[str]:
    """Return structured CR-08/FIND references from review finding text."""
    return frozenset((*_CR08_RE.findall(text), *_FINDING_RE.findall(text)))
