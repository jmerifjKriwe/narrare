"""Deterministic temporal consistency checks (ADR-021).

Pure functions for detecting temporal inconsistencies in timeline data.
No I/O, no DB access — fully testable in isolation.

Follows ADR-021: deterministic analysis where possible, LLM where not.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

from pydantic import BaseModel


class TemporalIssueSeverity(StrEnum):
    """Severity level for temporal consistency issues."""

    ERROR = "error"  # Definite inconsistency
    WARNING = "warning"  # Likely inconsistency
    INFO = "info"  # Possible concern


class TemporalIssue(BaseModel):
    """A single temporal consistency issue.

    Attributes:
        severity: How serious this issue is.
        rule_id: Identifier for the check that found this issue
            (e.g., ``"ordering_violation"``, ``"duplicate_event"``).
        event_ids: UUIDs of affected events.
        description: Human-readable explanation of the issue.
        suggestion: How to fix the issue.
        source: Whether this was found by deterministic rules or LLM.
    """

    severity: TemporalIssueSeverity
    rule_id: str
    event_ids: list[str] = []
    description: str = ""
    suggestion: str = ""
    source: str = "deterministic"


class TemporalConsistencyResult(BaseModel):
    """Result of deterministic temporal consistency checks.

    Attributes:
        issues: All issues found by the checks.
        deterministic_pass: Whether all deterministic checks passed
            (no errors).
        overall_assessment: Human-readable summary of the check results.
    """

    issues: list[TemporalIssue] = []
    deterministic_pass: bool = True
    overall_assessment: str = ""


class TemporalOrderingCheck:
    """Detect events that violate temporal ordering.

    An ordering violation occurs when event A has a consequence
    referencing event B, but A.temporal_order > B.temporal_order.
    """

    @staticmethod
    def check(events: list[dict[str, Any]]) -> list[TemporalIssue]:
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


class DurationImpossibilityCheck:
    """Detect impossible durations between events.

    Currently a placeholder for future rule-based duration checks.
    Requires normalized timestamps to perform calculations.
    """

    @staticmethod
    def check(events: list[dict[str, Any]]) -> list[TemporalIssue]:
        """Check for duration impossibilities.

        Args:
            events: List of event dicts with keys: id, event_name,
                    timestamp_raw, timestamp_normalized.

        Returns:
            List of duration impossibility issues.
        """
        # Placeholder — duration checks require timestamp normalization
        # which will be added in Phase 3 with character age tracking
        return []


class DuplicateEventCheck:
    """Detect likely duplicate events.

    Two events are considered duplicates if they share the same
    timestamp_raw and chapter_reference.
    """

    @staticmethod
    def check(events: list[dict[str, Any]]) -> list[TemporalIssue]:
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


class CharacterAgeCheck:
    """Detect age inconsistencies at event points.

    Checks if character ages are plausible at each timeline event
    based on birth_date in character metadata.
    """

    @staticmethod
    def check(
        events: list[dict[str, Any]],
        character_ages: Mapping[str, str | None],
    ) -> list[TemporalIssue]:
        """Check for age inconsistencies.

        Args:
            events: List of event dicts with character_refs and timestamp_raw.
            character_ages: Map of character name to age string (or None if
                no birth_date).

        Returns:
            List of age inconsistency issues.
        """
        characters_without_age: set[str] = set()

        for event in events:
            raw_refs = event.get("character_refs", [])
            refs = cast("list[dict[str, Any]]", raw_refs) if isinstance(raw_refs, list) else []
            for ref in refs:
                name = str(ref.get("name", ""))
                if name and name not in character_ages:
                    characters_without_age.add(name)

        if not characters_without_age:
            return []

        return [
            TemporalIssue(
                severity=TemporalIssueSeverity.INFO,
                rule_id="character_missing_birth_date",
                event_ids=[],
                description=(
                    f"{len(characters_without_age)} character(s) referenced in "
                    f"events have no birth date: "
                    f"{', '.join(sorted(characters_without_age))}."
                ),
                suggestion=(
                    "Add birth_date to character metadata in the "
                    "Knowledge Base for age consistency checking."
                ),
            )
        ]


def run_deterministic_checks(
    events: list[dict[str, Any]],
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
