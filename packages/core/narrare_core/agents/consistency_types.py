"""Output types for ConsistencyAgent.

See CONS-001 — cross-entity and cross-chapter consistency checking.
Detects contradictions in characters, timeline, world facts, and plot logic.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ConsistencyCheckType(StrEnum):
    """Type of consistency check to perform.

    Attributes:
        CHARACTER: Behavior, voice, knowledge, abilities consistency.
        TIMELINE: Event sequencing, durations, ages, temporal markers.
        WORLD: Location properties, system rules, faction relationships, geography.
        PLOT: Cause/effect chains, character motivations, setup/payoff, loose ends.
    """

    CHARACTER = "character"
    TIMELINE = "timeline"
    WORLD = "world"
    PLOT = "plot"


class ConsistencySeverity(StrEnum):
    """Severity of a consistency issue.

    Attributes:
        ERROR: Impossible contradiction (e.g., character alive in one chapter, dead in next).
        WARNING: Likely inconsistency (e.g., personality trait contradicts behavior).
        INFO: Minor discrepancy (e.g., slight age mismatch that might be intentional).
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ConsistencyIssue(BaseModel):
    """A single consistency issue found.

    Attributes:
        check_type: Which check type produced this issue.
        severity: How serious the issue is.
        description: Human-readable description of what's inconsistent.
        locations: Where the contradiction appears (chapter references or KB references).
        conflicting_facts: The facts that contradict each other.
        suggestion: Optional suggestion for how to resolve the issue.
        confidence: AI confidence score 0.0-1.0.
    """

    check_type: ConsistencyCheckType
    severity: ConsistencySeverity
    description: str
    locations: list[str]
    conflicting_facts: list[str]
    suggestion: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class ConsistencyDeps:
    """Dependencies for ConsistencyAgent.

    This is a plain class (not Pydantic) — follows the existing pattern
    used by ExtractionDeps, ReviewDeps, and SummaryDeps.

    Attributes:
        novel_id: The novel being checked.
        language: Language code for prompt construction.
        chapter_texts: Dict mapping chapter_id -> chapter_content to analyze.
        kb_entity_summaries: KB entity summaries for context. Each entry has
            entity_type, name, and fields dict.
        timeline_events: Timeline events for temporal consistency context.
            Each entry has event_name, timestamp, character, and location.
        check_types: Which check types to run. If empty, runs all.
        existing_issue_count: Number of previously found issues (for dedup context).
    """

    def __init__(
        self,
        language: str = "en",
        novel_id: str = "",
        chapter_texts: dict[str, str] | None = None,
        kb_entity_summaries: list[dict[str, object]] | None = None,
        timeline_events: list[dict[str, str]] | None = None,
        check_types: list[ConsistencyCheckType] | None = None,
        existing_issue_count: int = 0,
    ) -> None:
        self.language = language
        self.novel_id = novel_id
        self.chapter_texts = chapter_texts or {}
        self.kb_entity_summaries = kb_entity_summaries or []
        self.timeline_events = timeline_events or []
        self.check_types = check_types or list(ConsistencyCheckType)
        self.existing_issue_count = existing_issue_count


class ConsistencyOutput(BaseModel):
    """Structured output from ConsistencyAgent.

    Attributes:
        issues: List of consistency issues found, ordered by severity.
        overall_assessment: 1-2 sentence summary of overall consistency health.
        checked_types: Which check types were executed during this run.
    """

    issues: list[ConsistencyIssue] = []
    overall_assessment: str = ""
    checked_types: list[ConsistencyCheckType] = []
