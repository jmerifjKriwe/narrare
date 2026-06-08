"""Evidence override helpers for mode-level adoption scoring.

Refactored out of ``scorer_modes._check_runtime_requirements`` to respect
RULE-04 file size limits — consolidates 5 nearly identical blocks into a
single generic function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adoption.scorer_modes import RuntimeCheckDetail


def apply_evidence_override(
    details: list[RuntimeCheckDetail],
    all_verified: bool,
    evidence: dict[str, set[str]] | None,
    mode_feature_id: str | None,
    mode_name: str | None,
    requirement_name: str,
    verified_note: str,
    optional_requirement_name: str | None = None,
) -> tuple[list[RuntimeCheckDetail], bool]:
    """Apply a single evidence override pattern.

    If *evidence* is not *None* and *mode_name* is found in the evidence
    dict for *mode_feature_id*, sets the matching requirement's
    ``evidence_status`` to ``"verified"`` and updates the
    *all_verified* flag.

    When *optional_requirement_name* is provided, also overrides
    requirements whose ``requirement`` field matches it **and** whose
    ``declared`` field is ``"optional"`` — for cases where an optional
    requirement is implicitly satisfied by the same evidence.
    """
    if not (evidence and mode_feature_id and mode_name):
        return details, all_verified

    modes_for_feature = evidence.get(mode_feature_id)
    if mode_name not in (modes_for_feature or set()):
        return details, all_verified

    for detail in details:
        updated = False

        # Primary requirement override.
        if detail.requirement == requirement_name and detail.evidence_status == "missing":
            detail.evidence_status = "verified"
            detail.note = verified_note
            updated = True

        # Optional secondary requirement override (same evidence applies).
        if (
            optional_requirement_name
            and detail.requirement == optional_requirement_name
            and detail.declared == "optional"
            and detail.evidence_status == "missing"
        ):
            detail.evidence_status = "verified"
            detail.note = verified_note
            updated = True

        if updated and not all_verified:
            all_verified = all(d.evidence_status in ("verified", "not_applicable") for d in details)

    return details, all_verified
