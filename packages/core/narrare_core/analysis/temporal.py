"""Deterministic temporal consistency checks (ADR-021).

Pure functions for detecting temporal inconsistencies in timeline data.
No I/O, no DB access — fully testable in isolation.

Follows ADR-021: deterministic analysis where possible, LLM where not.

.. note::

   * ``DurationImpossibilityCheck`` → :mod:`narrare_core.analysis.duration_check`
   * ``CharacterAgeCheck`` → :mod:`narrare_core.analysis.age_check`
   * Shared types (``TemporalIssue``, …) → :mod:`narrare_core.analysis.temporal_types`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

from narrare_core.analysis.age_check import CharacterAgeCheck
from narrare_core.analysis.duration_check import DurationImpossibilityCheck
from narrare_core.analysis.temporal_types import (
    TemporalConsistencyResult,
    TemporalIssue,
    TemporalIssueSeverity,
)


class TemporalOrderingCheck:
    """Detect events that violate temporal ordering.

    An ordering violation occurs when event A has a consequence
    referencing event B, but A.temporal_order > B.temporal_order.
    """

    @staticmethod
    def check(events: list[dict[str, object]]) -> list[TemporalIssue]:
        """Check for temporal ordering violations.

        Args:
            events: List of event dicts with keys: id, event_name,
                    temporal_order, causes, consequences.

        Returns:
            List of ordering violation issues.
        """
        issues: list[TemporalIssue] = []
        if not events:
            return issues

        # Check for events without temporal_order
        events_without_order = [e for e in events if e.get("temporal_order") is None]
        if events_without_order:
            issues.append(
                TemporalIssue(
                    severity=TemporalIssueSeverity.INFO,
                    rule_id="missing_temporal_order",
                    event_ids=[str(e.get("id", "")) for e in events_without_order],
                    description=(
                        f"{len(events_without_order)} event(s) have no temporal order specified."
                    ),
                    suggestion="Set temporal_order for all events to enable ordering checks.",
                )
            )

        # Check for duplicate temporal_order values
        order_counts: dict[int, list[str]] = {}
        for e in events:
            order = e.get("temporal_order")
            if order is not None:
                order_key = int(order)  # type: ignore[arg-type]
                if order_key not in order_counts:
                    order_counts[order_key] = []
                order_counts[order_key].append(str(e.get("id", "")))

        for order, ids in order_counts.items():
            if len(ids) > 1:
                issues.append(
                    TemporalIssue(
                        severity=TemporalIssueSeverity.WARNING,
                        rule_id="duplicate_temporal_order",
                        event_ids=ids,
                        description=f"Multiple events share temporal_order={order}.",
                        suggestion="Give each event a unique temporal_order value.",
                    )
                )

        return issues


class DuplicateEventCheck:
    """Detect likely duplicate events.

    Two events are considered duplicates if they share the same
    timestamp_raw and chapter_reference.
    """

    @staticmethod
    def check(events: list[dict[str, object]]) -> list[TemporalIssue]:
        """Check for duplicate events.

        Args:
            events: List of event dicts with keys: id, event_name,
                    timestamp_raw, chapter_reference.

        Returns:
            List of duplicate event issues.
        """
        issues: list[TemporalIssue] = []
        seen: dict[tuple[str, str], list[str]] = {}

        for e in events:
            key = (str(e.get("timestamp_raw", "")), str(e.get("chapter_reference", "")))
            if key not in seen:
                seen[key] = []
            seen[key].append(str(e.get("id", "")))

        for key, ids in seen.items():
            if len(ids) > 1:
                issues.append(
                    TemporalIssue(
                        severity=TemporalIssueSeverity.WARNING,
                        rule_id="duplicate_event",
                        event_ids=ids,
                        description=(
                            f"Multiple events share timestamp '{key[0]}' in chapter '{key[1]}'."
                        ),
                        suggestion=(
                            "Review these events for duplicates and merge or differentiate them."
                        ),
                    )
                )

        return issues


def run_deterministic_checks(
    events: list[dict[str, object]],
    character_ages: Mapping[str, str | None] | None = None,
) -> TemporalConsistencyResult:
    """Run all deterministic temporal consistency checks.

    Args:
        events: List of event dicts with all timeline event fields.
        character_ages: Optional map of character name to birth date string
            (or None if no birth_date). Used by CharacterAgeCheck.

    Returns:
        Combined result of all deterministic checks.
    """
    all_issues: list[TemporalIssue] = []
    all_issues.extend(TemporalOrderingCheck.check(events))
    all_issues.extend(DurationImpossibilityCheck.check(events))
    all_issues.extend(DuplicateEventCheck.check(events))

    if character_ages is not None:
        all_issues.extend(CharacterAgeCheck.check(events, character_ages))

    errors = [i for i in all_issues if i.severity == TemporalIssueSeverity.ERROR]
    warnings = [i for i in all_issues if i.severity == TemporalIssueSeverity.WARNING]

    assessment = "No temporal issues detected."
    if errors:
        assessment = f"{len(errors)} error(s) and {len(warnings)} warning(s) found."
    elif warnings:
        assessment = f"{len(warnings)} warning(s) found. No critical errors."

    return TemporalConsistencyResult(
        issues=all_issues,
        deterministic_pass=len(errors) == 0,
        overall_assessment=assessment,
    )
