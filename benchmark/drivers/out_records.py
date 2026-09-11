"""Typed parsed records for the OUT-direction capability drivers (Task 9).

One frozen record per driver, mirroring the REAL response schemas they
are parsed from (per-record schema sources cited). Drivers keep only
the scoring-relevant fields; the complete raw payloads live in the
run's event sink (``benchmark.ingest_events``), so nothing is lost for
the artifacts. Lists become tuples for record immutability.

Schema sources (``apps/api/narrare/`` unless noted):

- ``EntrySummary`` / ``EntryBrowseRecord`` / ``SearchRecord`` —
  ``KBEntryResponse`` / ``KBEntryListResponse`` (``kb/schemas.py``,
  served by ``kb/router.py`` list/search, both paginated
  ``page``/``page_size``/``total``); ``AutocompleteHit`` — the plain
  ``list[dict[str, str]]`` rows (``id``/``name``/``entity_type``/
  ``slug``) of ``GET /kb/entries/autocomplete``
  (``kb/router_references.py`` + ``kb/service.py::autocomplete``).
- ``KbEntryDetail`` / ``RelationshipDetail`` / ``EntityDetailRecord`` —
  ``KBEntryResponse`` / ``KBRelationshipResponse``
  (``kb/schemas.py``) plus the ``{"rel_type", "inverse"}`` body of
  ``GET /kb/relationships/inverse-suggestion``
  (``kb/router_relationships.py``). COMPLETE projections: this is the
  KB-state fetch the Task-11 build-quality scorer consumes (entry
  identity/status/content/metadata + full relationship edges incl.
  enriched ``source_name``/``target_name``); only the timestamps are
  left to the raw sink.
- ``GraphNodeRef`` / ``GraphEdgeRef`` / ``GraphRecord`` —
  ``GraphNode`` / ``GraphEdge`` / ``GraphStats`` / ``GraphResponse`` /
  ``ShortestPathResponse`` (``kb/graph_schemas.py``); count dicts are
  carried as key-sorted tuple pairs for deterministic comparison.
- ``CanonEntryRef`` / ``CanonReadRecord`` — ``SeriesKBEntry``
  (``packages/core/narrare_core/kb/schemas/entry.py``; note the Core
  schema serializes its metadata column as ``metadata_``).
- ``WikiSummaryProse`` / ``WikiReadRecord`` — ``WikiIndexResponse`` /
  ``WikiSummaryListResponse`` / ``WikiSummaryResponse`` /
  ``WikiChapterSummaryResponse`` (``wiki/schemas.py``). The narrative
  prose fields are carried RAW — wiki read is a recorded-not-scored
  surface (plan Task 13; inventory 02-out "partially benchmarkable").
- ``TimelineEventRef`` / ``CharacterAge`` / ``TimelineReadRecord`` —
  ``TimelineEventCRUDResponse`` / ``CharacterAgeInfo`` /
  ``CharacterAgeReport`` (``planning/timeline_schemas.py``); the
  events list is NOT paginated (plain list response).
- ``Suggestion`` / ``SuggestionsRecord`` — ``KBSuggestionResponse``
  (``kb/schemas.py``, ``kb/router_suggestions.py``).
- ``ResolvedRef`` / ``ReferenceResolutionRecord`` —
  ``ReferenceResolution`` / ``ResolveReferencesResponse``
  (``kb/schemas.py``).
- ``TemplateInfo`` / ``TemplateDetail`` / ``TemplatesRecord`` —
  ``TemplateInfoResponse`` / ``TemplateDetailResponse``
  (``templates/schemas.py``); the detail's template ``content`` (YAML
  prompt-system material) stays in the raw sink.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntrySummary:
    """Scoring-relevant identity of one listed KB entry (``KBEntryResponse``)."""

    id: str
    name: str
    entity_type: str
    slug: str
    status: str
    review_status: str


@dataclass(frozen=True)
class AutocompleteHit:
    """One autocomplete row (plain ``dict[str, str]``, ``kb/service.py``)."""

    id: str
    name: str
    entity_type: str
    slug: str


@dataclass(frozen=True)
class EntryBrowseRecord:
    """CAP-OUT-01: full entry listing (all pages) + autocomplete probe."""

    entries: tuple[EntrySummary, ...]
    total: int
    pages_fetched: int
    autocomplete: tuple[AutocompleteHit, ...]


@dataclass(frozen=True)
class SearchRecord:
    """CAP-OUT-02: lexical search result pages for one probe query."""

    query: str
    entries: tuple[EntrySummary, ...]
    total: int
    pages_fetched: int


@dataclass(frozen=True)
class KbEntryDetail:
    """COMPLETE ``KBEntryResponse`` projection — the Task-11 scorer surface.

    Every schema field except the timestamps (raw sink) — identity,
    classification, lifecycle status, tags/metadata, and the entry
    ``body`` the fact matcher reads.
    """

    id: str
    novel_id: str
    entity_type: str
    name: str
    slug: str
    status: str
    tags: tuple[str, ...] | None
    metadata: dict[str, object] | None
    body: str | None
    template_version: str | None
    source: str
    review_status: str
    embeddings_dirty: bool


@dataclass(frozen=True)
class RelationshipDetail:
    """COMPLETE ``KBRelationshipResponse`` projection — scorer surface.

    Full edge incl. the enriched display names and the ``direction``
    qualifier; only the timestamps are left to the raw sink.
    """

    id: str
    rel_type: str
    source_id: str
    target_id: str
    label: str | None
    direction: str
    source_name: str | None
    target_name: str | None
    metadata: dict[str, object] | None


@dataclass(frozen=True)
class EntityDetailRecord:
    """CAP-OUT-03: the per-entity KB-state slice the Task-11 scorer consumes.

    Entry detail + its relationship edges + the inverse-rel-type lookup
    (queried for the FIRST relationship's type when one exists — the
    static inverse map needs a ``rel_type`` to ask about; an entity
    without relationships has none, so the lookup is skipped, not
    fabricated).
    """

    entry: KbEntryDetail
    relationships: tuple[RelationshipDetail, ...]
    inverse_of: str | None
    inverse_rel_type: str | None


@dataclass(frozen=True)
class GraphNodeRef:
    """Render-relevant node fields (``GraphNode``)."""

    id: str
    label: str
    entity_type: str
    degree: int


@dataclass(frozen=True)
class GraphEdgeRef:
    """Structural edge fields (``GraphEdge``; ``weight`` stays in the sink)."""

    id: str
    source: str
    target: str
    rel_type: str
    direction: str


@dataclass(frozen=True)
class GraphRecord:
    """CAP-OUT-04: graph nodes/edges + stats + shortest-path probe.

    Count dicts are key-sorted tuple pairs so record equality stays
    deterministic; the path probe runs between the first two graph
    nodes (skipped — not fabricated — when the graph has < 2 nodes).
    """

    nodes: tuple[GraphNodeRef, ...]
    edges: tuple[GraphEdgeRef, ...]
    entity_type_counts: tuple[tuple[str, int], ...]
    rel_type_counts: tuple[tuple[str, int], ...]
    isolated_count: int
    connected_components: int
    path: tuple[str, ...] | None
    path_length: int | None


@dataclass(frozen=True)
class CanonEntryRef:
    """Series-canon entry identity (``SeriesKBEntry``; ``scope`` literal)."""

    id: str
    name: str
    entity_type: str
    slug: str
    scope: str


@dataclass(frozen=True)
class CanonReadRecord:
    """CAP-OUT-05: series-canon listing + read-back of the first entry."""

    series_id: str
    entries: tuple[CanonEntryRef, ...]
    single: CanonEntryRef | None


@dataclass(frozen=True)
class WikiSummaryProse:
    """One entity summary; the narrative prose is carried RAW.

    Recorded-not-scored surface (plan Task 13): presence/status are
    mechanically scorable, the ``narrative_summary`` text is recorded
    for the artifacts (an LLM judge would be declared in the manifest).
    """

    entity_id: str
    status: str
    narrative_summary: str
    role_in_story: str | None


@dataclass(frozen=True)
class WikiReadRecord:
    """CAP-OUT-06: wiki index health + summaries + chapter summary.

    ``single``/``chapter_summary`` are None when no entity target /
    ingested chapter exists — those sub-reads are skipped, not made up.
    """

    total_summaries: int
    fresh_count: int
    stale_count: int
    pending_count: int
    summaries: tuple[WikiSummaryProse, ...]
    single: WikiSummaryProse | None
    chapter_summary: str | None
    chapter_summary_status: str | None


@dataclass(frozen=True)
class TimelineEventRef:
    """Scoring-relevant event fields (``TimelineEventCRUDResponse``)."""

    id: str
    event_name: str
    event_type: str
    timestamp_raw: str
    source: str
    confidence: float | None
    is_confirmed: bool
    chapter_id: str | None


@dataclass(frozen=True)
class CharacterAge:
    """One character's age info (``CharacterAgeInfo``)."""

    character_name: str
    character_id: str | None
    birth_date: str | None
    birth_date_narrative: str | None
    age_available: bool


@dataclass(frozen=True)
class TimelineReadRecord:
    """CAP-OUT-07: event list + read-back of the first + age report."""

    events: tuple[TimelineEventRef, ...]
    single: TimelineEventRef | None
    ages: tuple[CharacterAge, ...]
    characters_with_age: int
    characters_without_age: int


@dataclass(frozen=True)
class Suggestion:
    """One ranked proactive suggestion (``KBSuggestionResponse``).

    ``last_referenced_at`` stays in the raw sink (timestamp).
    """

    entry_id: str
    entry_type: str
    name: str
    relevance_score: float
    similarity: float
    usage_count: int
    reason: str


@dataclass(frozen=True)
class SuggestionsRecord:
    """CAP-OUT-08: ranked proactive KB suggestions for one chapter."""

    chapter_id: str
    suggestions: tuple[Suggestion, ...]


@dataclass(frozen=True)
class ResolvedRef:
    """One resolved @-mention (``ReferenceResolution``)."""

    mention: str
    entry_id: str | None
    entry_name: str | None
    entity_type: str | None
    slug: str | None


@dataclass(frozen=True)
class ReferenceResolutionRecord:
    """CAP-OUT-09: @-mention resolution over the reference-derived probe."""

    resolved: tuple[ResolvedRef, ...]
    html: str | None


@dataclass(frozen=True)
class TemplateInfo:
    """Template-override metadata (``TemplateInfoResponse``)."""

    entity_type: str
    scope: str
    schema_version: str
    has_override: bool
    has_update: bool


@dataclass(frozen=True)
class TemplateDetail:
    """Template detail read-back (``TemplateDetailResponse``).

    ``content``/``base_content`` (YAML prompt-system material) stay in
    the raw sink — not KB content, nothing to score.
    """

    entity_type: str
    scope: str
    schema_version: str
    based_on_version: str | None
    is_overridden: bool


@dataclass(frozen=True)
class TemplatesRecord:
    """CAP-OUT-10: template-type listing + read-back of the first type."""

    templates: tuple[TemplateInfo, ...]
    detail: TemplateDetail | None
