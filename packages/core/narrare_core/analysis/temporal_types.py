"""Shared types for deterministic temporal consistency checks.

Type models used across all temporal check modules:
``DurationImpossibilityCheck``, ``CharacterAgeCheck``,
``TemporalOrderingCheck``, and ``DuplicateEventCheck``.

Extracted from ``temporal.py`` to resolve RULE-04 (file-size limit).
"""

from __future__ import annotations

from enum import StrEnum

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
