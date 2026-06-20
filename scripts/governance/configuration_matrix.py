"""Configuration Adoption Matrix validator (ADR-051).

Single responsibility (RULE-06): validate the Configuration Adoption Matrix
manifest against the ADR-051 source -> resolver -> runtime-consumer ->
evidence contract and produce a status-bearing report.

This is the *policy layer*. Type definitions, controlled vocabularies, and
YAML parsing live in :mod:`_matrix_types` (extracted for RULE-04). This
module imports NO application runtime modules (RULE-07); evidence paths are
recorded as strings and asserted by the test suite / CI, not imported here.

Spec: docs/features/remediation/cr-08-configuration-effect-drift.md
ADR:  docs/architecture/decisions/ADR-051-configuration-effect-adoption-contract.md
"""

from __future__ import annotations

from governance._matrix_review_gate import validate_review_finding_matrix_coverage
from governance._matrix_types import (
    CLASSIFICATIONS,
    LIFECYCLE_STATES,
    REQUIRED_FIELDS,
    Classification,
    Lifecycle,
    MatrixEntry,
    MatrixReport,
    MatrixStatus,
    Violation,
    load_matrix,
    parse_matrix,
)

__all__ = [
    "Classification",
    "Lifecycle",
    "MatrixEntry",
    "MatrixReport",
    "MatrixStatus",
    "Violation",
    "load_matrix",
    "parse_matrix",
    "validate_matrix",
    "validate_review_finding_matrix_coverage",
]

# ---------------------------------------------------------------------------
# Validation thresholds
# ---------------------------------------------------------------------------

#: Classifications that demand a proven runtime consumer + evidence (P0 gate).
_EFFECTIVE_CLASSIFICATIONS: frozenset[str] = frozenset(
    {Classification.USER.value, Classification.PROJECT.value}
)

#: Lifecycle states that must carry non-empty enforcement_evidence.
_EVIDENCE_REQUIRED_LIFECYCLES: frozenset[str] = frozenset({Lifecycle.ADOPTED.value})


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_matrix(
    entries: list[MatrixEntry],
    expected_ids: list[str],
) -> MatrixReport:
    """Validate entries against the ADR-051 contract.

    Rules (each produces a :class:`Violation`):

    1. Every required field is present and non-empty per entry.
    2. ``classification`` and ``lifecycle`` are valid ADR-051 values.
    3. ``setting_id`` values are unique.
    4. Every ``expected_setting_ids`` entry appears in ``entries``.
    5. No entry references an id outside ``expected_setting_ids`` (typo guard).
    6. ``user``/``project`` classifications require ``runtime_consumer``.
    7. ``user``/``project`` classifications require non-empty
       ``enforcement_evidence`` — unless the entry is a tracked
       ``formal_finding`` (with a ``cr_task``/``finding`` reference), which
       is an acknowledged gap rather than a silent false control.
    8. ``adopted`` lifecycle requires non-empty ``enforcement_evidence``.
    9. ``formal_finding`` lifecycle requires a ``cr_task`` or ``finding``
       reference (no untracked prose debt).
    """
    violations: list[Violation] = list(_check_field_and_enum_validity(entries))
    violations.extend(_check_id_coverage(entries, expected_ids))

    status = MatrixStatus.PASS if not violations else MatrixStatus.FAIL
    return MatrixReport(
        status=status,
        total_entries=len(entries),
        expected_count=len(expected_ids),
        violations=tuple(violations),
    )


def _check_field_and_enum_validity(entries: list[MatrixEntry]) -> list[Violation]:
    """Rules 1, 2, 6, 7, 8, 9 — per-entry field/enum/evidence checks."""
    out: list[Violation] = []
    for entry in entries:
        sid = entry.setting_id or "<missing setting_id>"

        out.extend(_check_required_fields(entry, sid))
        out.extend(_check_vocabularies(entry, sid))
        out.extend(_check_effective_adoption(entry, sid))
        out.extend(_check_lifecycle_evidence(entry, sid))
    return out


def _check_required_fields(entry: MatrixEntry, sid: str) -> list[Violation]:
    """Rule 1 — required fields present and non-empty."""
    out: list[Violation] = []
    for field_name in REQUIRED_FIELDS:
        value = getattr(entry, field_name)
        if not isinstance(value, str) or not value.strip():
            out.append(
                Violation(
                    rule="required_field",
                    setting_id=sid,
                    message=f"missing required field '{field_name}'",
                )
            )
    return out


def _check_vocabularies(entry: MatrixEntry, sid: str) -> list[Violation]:
    """Rule 2 — controlled vocabularies."""
    out: list[Violation] = []
    if entry.classification and entry.classification not in CLASSIFICATIONS:
        out.append(
            Violation(
                rule="invalid_classification",
                setting_id=sid,
                message=(
                    f"classification '{entry.classification}' is not one "
                    f"of {sorted(CLASSIFICATIONS)}"
                ),
            )
        )
    if entry.lifecycle and entry.lifecycle not in LIFECYCLE_STATES:
        out.append(
            Violation(
                rule="invalid_lifecycle",
                setting_id=sid,
                message=(f"lifecycle '{entry.lifecycle}' is not one of {sorted(LIFECYCLE_STATES)}"),
            )
        )
    return out


def _check_effective_adoption(entry: MatrixEntry, sid: str) -> list[Violation]:
    """Rules 6, 7, 9 — user/project adoption + formal-finding tracking.

    A user/project setting is a *silent false control* unless it either
    carries enforcement_evidence OR is a tracked formal_finding. Tracked
    findings are acknowledged gaps, not silent drift.
    """
    out: list[Violation] = []
    if entry.classification in _EFFECTIVE_CLASSIFICATIONS:
        if not (entry.runtime_consumer and entry.runtime_consumer.strip()):
            out.append(
                Violation(
                    rule="missing_runtime_consumer",
                    setting_id=sid,
                    message=(
                        f"classification '{entry.classification}' requires a runtime_consumer"
                    ),
                )
            )
        is_tracked_finding = entry.lifecycle == Lifecycle.FORMAL_FINDING.value and bool(
            entry.cr_task or entry.finding
        )
        if not entry.enforcement_evidence and not is_tracked_finding:
            out.append(
                Violation(
                    rule="missing_enforcement_evidence",
                    setting_id=sid,
                    message=(
                        f"classification '{entry.classification}' requires "
                        "non-empty enforcement_evidence or a tracked "
                        "formal_finding (cr_task/finding)"
                    ),
                )
            )

    # Rule 9 — a formal_finding must be tracked, regardless of classification.
    if entry.lifecycle == Lifecycle.FORMAL_FINDING.value and not (entry.cr_task or entry.finding):
        out.append(
            Violation(
                rule="formal_finding_without_tracking",
                setting_id=sid,
                message="lifecycle 'formal_finding' requires a cr_task or finding reference",
            )
        )
    return out


def _check_lifecycle_evidence(entry: MatrixEntry, sid: str) -> list[Violation]:
    """Rule 8 — adopted values must carry evidence."""
    if entry.lifecycle in _EVIDENCE_REQUIRED_LIFECYCLES and not entry.enforcement_evidence:
        return [
            Violation(
                rule="adopted_without_evidence",
                setting_id=sid,
                message="lifecycle 'adopted' requires non-empty enforcement_evidence",
            )
        ]
    return []


def _check_id_coverage(
    entries: list[MatrixEntry],
    expected_ids: list[str],
) -> list[Violation]:
    """Rules 3, 4, 5 — uniqueness and expected-id coverage."""
    out: list[Violation] = []

    # Rule 3 — unique setting_ids.
    seen: dict[str, int] = {}
    for entry in entries:
        sid = entry.setting_id
        if not sid:
            continue
        seen[sid] = seen.get(sid, 0) + 1
    for sid, count in seen.items():
        if count > 1:
            out.append(
                Violation(
                    rule="duplicate_setting_id",
                    setting_id=sid,
                    message=f"setting_id appears {count} times",
                )
            )

    entry_ids = {entry.setting_id for entry in entries if entry.setting_id}
    expected_set = set(expected_ids)

    # Rule 4 — every expected id must be classified.
    for missing in sorted(expected_set - entry_ids):
        out.append(
            Violation(
                rule="unclassified_setting",
                setting_id=missing,
                message="expected_setting_id has no matrix entry (unclassified)",
            )
        )

    # Rule 5 — no entry id outside the expected list (typo guard).
    for extra in sorted(entry_ids - expected_set):
        out.append(
            Violation(
                rule="unexpected_setting_id",
                setting_id=extra,
                message="entry setting_id is not in expected_setting_ids (typo?)",
            )
        )
    return out
