"""Output types for TimelineAgent.

See ADR-015 Phase 2.1 — Output Types.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TimelineEvent(BaseModel):
    """A single event in the narrative timeline.

    Attributes:
        event_name: Short event name.
        description: What happens during this event.
        timestamp: Relative or absolute time reference.
        chapter_reference: Chapter reference linking to a source.
        characters_involved: Names of characters present.
        location: Where the event takes place.
        causes: What triggered this event.
        consequences: What follows from this event.
    """

    event_name: str = ""
    description: str = ""
    timestamp: str = ""
    chapter_reference: str = ""
    characters_involved: list[str] = []
    location: str = ""
    causes: list[str] = []
    consequences: list[str] = []


class TimelineOutput(BaseModel):
    """Structured output of a TimelineAgent run.

    Attributes:
        timeline_events: Chronologically ordered events.
        temporal_conflicts: Inconsistencies found in the timeline.
        coverage_gaps: Time periods or causal links that are missing.
        overall_assessment: 1-2 sentence evaluation of timeline quality.
        metadata: Additional metadata (model info, tokens, etc.).
    """

    timeline_events: list[TimelineEvent] = []
    temporal_conflicts: list[str] = []
    coverage_gaps: list[str] = []
    overall_assessment: str = ""
    metadata: dict[str, Any] = {}
