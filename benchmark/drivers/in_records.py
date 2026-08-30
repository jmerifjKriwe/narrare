"""Typed parsed records for the IN-direction capability drivers (Task 8).

One frozen record per driver, mirroring the REAL response schemas they
are parsed from (the OPEN-2 deferral is resolved here — per-record
schema sources cited). Drivers keep only the scoring-relevant fields;
the complete raw payloads live in the run's event sink
(``benchmark.ingest_events``), so nothing is lost for the artifacts.

Schema sources (``apps/api/narrare/`` unless noted):

- ``ExtractionCandidate`` — ``ExtractionItem``
  (``packages/core/narrare_core/agents/extraction_types.py``), the item
  shape of ``POST /kb/extract/{chapter_id}`` (``kb/router_extraction.py``).
- ``EntryRef`` / ``ExtractionRecord`` — ``ApplyExtractionEntryResult`` /
  ``ApplyExtractionResponse`` (``kb/schemas_extraction.py``); ``EntryRef``
  is reused for the manual-authoring responses (``KBEntryResponse``,
  ``kb/schemas.py``; ``SeriesKBEntry``, ``packages/core/narrare_core/kb/schemas/entry.py``).
- ``AssistSessionRecord`` — the ``KBCreationSession`` dump plus
  ``KBSessionCompleteResponse`` (``kb/session_models.py``,
  ``kb/session_schemas.py``, ``kb/router_sessions.py``,
  ``kb/router_sessions_complete.py``).
- ``ImproveRecord`` — ``KBImproveAnalysisResponse`` /
  ``KBImproveApplyResponse`` (``kb/improve_contracts.py``).
- ``WorldbuildingRecord`` — ``WorldbuildingAnalysisResponse`` /
  ``WorldbuildingApplyResponse`` (``kb/worldbuilding_contracts.py``).
- ``RelationshipRef`` — ``KBRelationshipResponse`` (``kb/schemas.py``).
- ``ScopeMoveRecord`` — ``JoinPreview`` / ``JoinResult``
  (``series/schemas.py``) plus the ``SeriesKBEntry`` / ``NovelKBEntry``
  scope literals (``packages/core/narrare_core/kb/schemas/entry.py``).
- ``ExtractedExpression`` / ``TimelineExtractionRecord`` —
  ``ExtractedEventResponse``, ``ConfirmExtractionRequest`` and
  ``TimelineEventCRUDResponse`` (``planning/timeline_schemas.py``).
- ``WikiRefreshRecord`` — ``WikiRefreshResponse`` (``wiki/schemas.py``)
  plus the mark-stale ``{"affected_count": int}`` body
  (``wiki/router.py``).
- ``VoiceProfile`` / ``CharacterVoiceRecord`` — ``CharacterVoiceResult``
  payloads of the flavor-B stream (``analysis/schemas_character_voice.py``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionCandidate:
    """One extraction result item (``ExtractionItem``, map §4.3.1)."""

    item_type: str
    name: str
    confidence: float
    source_text: str
    entity_type: str | None
    proposed_content: dict[str, object] | None
    target_entity_id: str | None
    relationship_type: str | None
    related_entity_name: str | None
    conflict_description: str | None


@dataclass(frozen=True)
class EntryRef:
    """Identity triple of a created/updated KB entry."""

    id: str
    name: str
    entity_type: str


@dataclass(frozen=True)
class RelationshipRef:
    """Identity of a created KB relationship (``KBRelationshipResponse``)."""

    id: str
    rel_type: str
    source_id: str
    target_id: str


@dataclass(frozen=True)
class ExtractionRecord:
    """CAP-IN-01: post-build re-extraction + endorse-all apply outcome."""

    chapter_id: str
    candidates: tuple[ExtractionCandidate, ...]
    analysis_notes: str
    created: tuple[str, ...]
    updated: tuple[str, ...]


@dataclass(frozen=True)
class AssistSessionRecord:
    """CAP-IN-02: driven session lifecycle and its created entry."""

    session_id: str
    entity_type: str
    status: str
    entry_id: str


@dataclass(frozen=True)
class ImproveRecord:
    """CAP-IN-03: improve analysis summary + apply outcome."""

    entry_id: str
    suggestion_count: int
    completeness_score: float
    overall_assessment: str
    applied_count: int
    apply_success: bool
    apply_message: str


@dataclass(frozen=True)
class WorldbuildingRecord:
    """CAP-IN-04: worldbuilding analysis counts + connection apply outcome."""

    gap_count: int
    connection_count: int
    consistency_count: int
    worldbuilding_score: float
    applied_indices: tuple[int, ...]
    created_count: int
    failed_count: int


@dataclass(frozen=True)
class ManualAuthoringRecord:
    """CAP-IN-05: authored entries and relationship (series parts optional)."""

    novel_entry: EntryRef
    series_entry: EntryRef | None
    relationship: RelationshipRef | None


@dataclass(frozen=True)
class ScopeMoveRecord:
    """CAP-IN-06: series join, promote (→ series) and demote (→ novel)."""

    series_id: str
    canon_empty: bool
    treatment_count: int
    join_position: int
    promoted_count: int
    entry_id: str
    promoted_scope: str
    demoted_scope: str


@dataclass(frozen=True)
class ExtractedExpression:
    """One flavor-A stream item (``ExtractedEventResponse``)."""

    id: str
    expression: str
    event_name: str
    timestamp_raw: str
    chapter_reference: str
    character_names: tuple[str, ...]
    location_name: str
    confidence: float
    context: str


@dataclass(frozen=True)
class TimelineExtractionRecord:
    """CAP-IN-07: collected expressions + the confirmed timeline event."""

    expressions: tuple[ExtractedExpression, ...]
    confirmed_event_id: str | None
    confirmed_event_name: str | None


@dataclass(frozen=True)
class WikiRefreshRecord:
    """CAP-IN-08: refresh outcome + mark-stale affected count."""

    summary_id: str | None
    status: str
    message: str
    affected_count: int


@dataclass(frozen=True)
class VoiceProfile:
    """One per-character result of the character-voice stream."""

    character_name: str
    kb_entry_id: str | None
    has_voice_analysis: bool
    distinctiveness_notes: str | None


@dataclass(frozen=True)
class CharacterVoiceRecord:
    """CAP-IN-09: collected per-character voice profiles + progress trail."""

    characters: tuple[VoiceProfile, ...]
    progress_messages: tuple[str, ...]
