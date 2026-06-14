"""ADR-045 adoption report status semantics.

Keeps runtime-adoption status policy separate from static score arithmetic so
``scorer.py`` remains focused on scoring and below RULE-04 limits.
"""

from __future__ import annotations

from typing import Any

PASS_THRESHOLD = 0.85
WARN_THRESHOLD = 0.70

STATUS_PASS = "PASS"  # nosec  # not a password; ADR-025 status constant
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"
STATUS_STATIC_ONLY = "STATIC_ONLY"
STATUS_GOVERNED_DEBT = "GOVERNED_DEBT"

_NON_PASSING_STATIC_STATUSES = {STATUS_WARN, STATUS_FAIL}
_REQUIRED_RUNTIME_DECLARATIONS = {"required", "budget_rejected"}


def status(score: float) -> str:
    """Return the static score status for ADR-025 scoring thresholds."""
    if score >= PASS_THRESHOLD:
        return STATUS_PASS
    if score >= WARN_THRESHOLD:
        return STATUS_WARN
    return STATUS_FAIL


def mode_requires_runtime(mode: Any) -> bool:
    """Return whether a mode has a required runtime-adoption contract."""
    return bool(getattr(mode, "requires_runtime_evidence", False)) and any(
        getattr(detail, "declared", "") in _REQUIRED_RUNTIME_DECLARATIONS
        for detail in getattr(mode, "runtime_details", [])
    )


def mode_has_runtime_gap(mode: Any) -> bool:
    """Return whether a runtime-required mode has not reached adoption."""
    return mode_requires_runtime(mode) and not bool(getattr(mode, "adopted", False))


def classify_category_status(
    static_status: str,
    modes: list[Any],
    *,
    evidence_source_declared: bool,
) -> str:
    """Cap a static category status with ADR-045 runtime semantics."""
    if static_status in _NON_PASSING_STATIC_STATUSES:
        return static_status
    if not any(mode_requires_runtime(mode) for mode in modes):
        return static_status
    if not evidence_source_declared:
        return STATUS_STATIC_ONLY
    if any(mode_has_runtime_gap(mode) for mode in modes):
        return STATUS_GOVERNED_DEBT
    return static_status


def classify_report_status(
    static_status: str,
    categories: list[Any],
    *,
    evidence_source_declared: bool,
) -> str:
    """Cap the overall static report status with ADR-045 runtime semantics."""
    if static_status in _NON_PASSING_STATIC_STATUSES:
        return static_status
    modes = [mode for category in categories for mode in getattr(category, "modes", [])]
    if not any(mode_requires_runtime(mode) for mode in modes):
        return static_status
    if not evidence_source_declared:
        return STATUS_STATIC_ONLY
    if any(mode_has_runtime_gap(mode) for mode in modes):
        return STATUS_GOVERNED_DEBT
    return static_status


def runtime_gap_count(categories: list[Any]) -> int:
    """Count runtime-required modes that are not adopted."""
    return sum(
        1
        for category in categories
        for mode in getattr(category, "modes", [])
        if mode_has_runtime_gap(mode)
    )
