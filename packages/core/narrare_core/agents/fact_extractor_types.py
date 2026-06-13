"""Types for FactExtractorAgent — structured fact extraction with provenance.

Defines the data contract for the staged consistency pipeline (ADR-044):
- ExtractedFact: structured intermediate representation with source provenance
- TimelineEventEnvelope: enriched timeline data preserving FIND-009 metadata
- FactExtractorDeps: agent dependencies
- FactExtractorOutput: agent output
- FactExtractorProtocol: contract for the fact extractor (RULE-03)

See ADR-044 — Staged Multi-Agent Consistency Pipeline.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# FactType — category of an extracted fact
# ---------------------------------------------------------------------------

type FactType = Literal[
    "character_state",
    "event",
    "location_state",
    "relationship",
    "ability",
    "timeline_marker",
]
"""Category of an extracted fact.

- ``character_state``: Physical or psychological state of a character.
- ``event``: An occurrence in the story world.
- ``location_state``: Properties or state of a location.
- ``relationship``: Relationship between entities.
- ``ability``: A skill, power, or capability.
- ``timeline_marker``: A temporal reference (before/after, duration, etc.).
"""


# ---------------------------------------------------------------------------
# ExtractedFact — structured intermediate representation
# ---------------------------------------------------------------------------


class ExtractedFact(BaseModel):
    """A single fact extracted from a source, with provenance.

    This is the core intermediate representation (IR) for the staged
    consistency pipeline. Every extracted fact carries its source location,
    confidence, and entity references so downstream agents can reason about
    *why* a fact exists.

    Attributes:
        fact_type: Category of the extracted fact.
        subject: The primary entity the fact is about (e.g. "Anna").
        predicate: The relationship or action described (e.g. "has eye color").
        object_value: The target of the relationship (e.g. "green eyes").
        chapter_id: Chapter where this fact was found.
        evidence_text: Exact quote from source prose supporting this fact.
        confidence: Extraction confidence 0.0-1.0.
        temporal_marker: Optional temporal reference (e.g. "before the battle").
    """

    fact_type: FactType
    subject: str
    predicate: str
    object_value: str
    chapter_id: str
    evidence_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    temporal_marker: str | None = None


# ---------------------------------------------------------------------------
# TimelineEventEnvelope — enriched timeline with provenance (FIND-009)
# ---------------------------------------------------------------------------


class TimelineEventEnvelope(BaseModel):
    """Rich timeline event with full provenance — FIND-009 integration contract.

    Preserves all metadata from the timeline module so downstream agents
    (ConsistencyAgent, FactExtractorAgent) can reason about causality,
    confidence, and source provenance.

    Attributes:
        event_id: Unique identifier for the event.
        event_name: Human-readable event name.
        timestamp_raw: Original timestamp text from source.
        timestamp_normalized: Normalized timestamp for comparison.
        temporal_order: Sequence order among all timeline events.
        source_chapter_id: Chapter where this event originates.
        character_refs: Characters involved with status metadata.
        location_ref: Location with status metadata, or None.
        causes: What caused this event.
        consequences: What this event caused.
        source: Source type (narration, dialogue, etc.).
        confidence: Confidence score 0.0-1.0.
        is_confirmed: Whether the event is confirmed by narration.
        kb_entity_status: Mapping of entity name to KB liveness status. Backends
            may report ``"unknown"`` when the upstream source cannot prove
            renamed or deleted state.
    """

    event_id: str
    event_name: str
    timestamp_raw: str
    timestamp_normalized: str | None = None
    temporal_order: int | None = None
    source_chapter_id: str | None = None
    character_refs: list[dict[str, str]] = []
    location_ref: dict[str, str] | None = None
    causes: list[str] = []
    consequences: list[str] = []
    source: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    is_confirmed: bool = True
    kb_entity_status: dict[str, str] = {}
    """Maps entity names to their KB status.

    Valid values: ``"active"``, ``"renamed"``, ``"deprecated"``, ``"deleted"``,
    or ``"unknown"`` when upstream liveness data is unavailable.
    Used by downstream agents to weight entity references.
    """


# ---------------------------------------------------------------------------
# Agent dependencies and output
# ---------------------------------------------------------------------------


class FactExtractorDeps:
    """Dependencies for FactExtractorAgent.

    Plain class (not Pydantic) — follows the existing pattern used by
    ConsistencyDeps, ExtractionDeps, ReviewDeps, and SummaryDeps.

    Attributes:
        chapter_texts: Dict mapping chapter_id -> chapter_content to analyze.
        kb_entity_names: Names of known KB entities for reference matching.
        kb_entity_summaries: KB entity summaries for context.
        timeline_envelopes: Enriched timeline events with provenance.
        language: Language code for output (default ``"en"``).
        genre: Project genre for context.
    """

    def __init__(
        self,
        chapter_texts: dict[str, str] | None = None,
        kb_entity_names: list[str] | None = None,
        kb_entity_summaries: list[dict[str, object]] | None = None,
        timeline_envelopes: list[TimelineEventEnvelope] | None = None,
        language: str = "en",
        genre: str = "",
    ) -> None:
        self.chapter_texts = chapter_texts or {}
        self.kb_entity_names = kb_entity_names or []
        self.kb_entity_summaries = kb_entity_summaries or []
        self.timeline_envelopes = timeline_envelopes or []
        self.language = language
        self.genre = genre


class FactExtractorOutput(BaseModel):
    """Structured output from FactExtractorAgent.

    Attributes:
        facts: List of extracted facts with provenance and confidence.
        assessment_summary: Agent's overall observations about extraction quality.
    """

    facts: list[ExtractedFact] = []
    assessment_summary: str = ""


# ---------------------------------------------------------------------------
# Contract (RULE-03)
# ---------------------------------------------------------------------------


@runtime_checkable
class FactExtractorProtocol(Protocol):
    """Protocol for fact extraction — RULE-03 contract.

    Any fact extractor must accept a prompt and FactExtractorDeps,
    and return a FactExtractorOutput. Enables test mocking and
    future alternative implementations.
    """

    async def run(
        self,
        prompt: str,
        deps: FactExtractorDeps,
        **kwargs: Any,
    ) -> FactExtractorOutput: ...
