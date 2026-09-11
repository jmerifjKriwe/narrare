"""Shared fixture backend for the OUT-direction driver tests (Task 9).

Scripted responders + fixture bodies speaking the verified response
shapes (``benchmark/docs/api-surface.md`` §7; per-shape sources are
cited in ``benchmark.drivers.out_records``). Plain helpers — no
fixtures, no network. Split out of the test modules per RULE-04
(predecessor pattern: ``in_direction_helpers.py``). The constant
fixtures (``ENTRY_BODY``, ``RELATIONSHIP_BODY``, timeline event body,
path prefixes) are reused from ``in_direction_helpers`` verbatim — same
KB shapes, one source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from benchmark.corpus_loader import Corpus, Reference
from benchmark.corpus_views import Entity
from benchmark.drivers.base import CapabilityContext, CapabilityStatus, CapabilityTimings
from benchmark.tests.client_helpers import RecordedCall, Responder, ScriptedApi, make_client
from benchmark.tests.in_direction_helpers import (
    ANALYSIS_BODIES,
    ENTRY_BODY,
    KB,
    NOVEL_ID,
    RELATIONSHIP_BODY,
    TIMELINE,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from benchmark.client import BenchmarkClient
    from benchmark.drivers.base import CapabilityDriver
    from benchmark.ingest_events import IngestEvent

# ---------------------------------------------------------------------------
# Path constants (registry EndpointSpec templates, /api/v1-joined)
# ---------------------------------------------------------------------------

KB_ENTRIES = f"{KB}/entries"
KB_SEARCH = f"{KB}/entries/search"
KB_AUTOCOMPLETE = f"{KB}/entries/autocomplete"
KB_DETAIL = f"{KB}/entries/entry-9"
KB_RELATIONSHIPS = f"{KB}/entries/entry-9/relationships"
KB_INVERSE = f"{KB}/relationships/inverse-suggestion"
KB_GRAPH = f"{KB}/graph"
KB_SHORTEST_PATH = f"{KB}/graph/shortest-path"
KB_SUGGESTIONS = f"{KB}/suggestions/chapter-1"
KB_RESOLVE = f"{KB}/resolve-references"
KB_TEMPLATES = f"{KB}/templates"
CANON = "/api/v1/series/series-1/kb"
CANON_ENTRY_PATH = f"{CANON}/entry-1"
WIKI = f"/api/v1/novels/{NOVEL_ID}/wiki"
EVENTS = f"{TIMELINE}/events"
EVENT_PATH = f"{TIMELINE}/events/event-1"
CHARACTER_AGES = f"{TIMELINE}/character-ages"

# ---------------------------------------------------------------------------
# Fixture bodies — schema-faithful per the cited response schemas
# ---------------------------------------------------------------------------

ENTRY_A: dict[str, object] = ENTRY_BODY
ENTRY_B: dict[str, object] = {
    **ENTRY_BODY,
    "id": "entry-2",
    "name": "HafenCity",
    "entity_type": "location",
    "slug": "hafen city",
}
ENTRY_C: dict[str, object] = {
    **ENTRY_BODY,
    "id": "entry-3",
    "name": "Zollamt",
    "entity_type": "organisation",
    "slug": "zollamt",
}
LIST_SINGLE_PAGE: dict[str, object] = {
    "items": [ENTRY_A, ENTRY_B],
    "total": 2,
    "page": 1,
    "page_size": 100,
}
LIST_PAGE_ONE: dict[str, object] = {
    "items": [ENTRY_A, ENTRY_B] * 50,  # a FULL page (API page_size cap = 100)
    "total": 101,
    "page": 1,
    "page_size": 100,
}
LIST_PAGE_TWO: dict[str, object] = {"items": [ENTRY_C], "total": 101, "page": 2, "page_size": 100}
AUTOCOMPLETE_BODY: list[object] = [
    {"id": "entry-9", "name": "Anna Meyer", "entity_type": "character", "slug": "anna-meyer"}
]
REL_BODY: dict[str, object] = {
    **RELATIONSHIP_BODY,
    "rel_type": "lives_in",
    "source_name": "Anna Meyer",
    "target_name": "HafenCity",
}
RELATIONSHIPS_BODY: list[object] = [REL_BODY]
INVERSE_BODY: dict[str, object] = {"rel_type": "lives_in", "inverse": "inhabited_by"}
GRAPH_NODE_A: dict[str, object] = {
    "id": "entry-9",
    "label": "Anna Meyer",
    "entity_type": "character",
    "status": "draft",
    "tags": None,
    "metadata": None,
    "degree": 1,
}
GRAPH_NODE_B: dict[str, object] = {
    "id": "entry-2",
    "label": "HafenCity",
    "entity_type": "location",
    "status": "approved",
    "tags": None,
    "metadata": None,
    "degree": 1,
}
GRAPH_BODY: dict[str, object] = {
    "nodes": [GRAPH_NODE_A, GRAPH_NODE_B],
    "edges": [
        {
            "id": "rel-1",
            "source": "entry-9",
            "target": "entry-2",
            "label": None,
            "rel_type": "lives_in",
            "direction": "directed",
            "weight": 1.0,
        }
    ],
    "stats": {
        "node_count": 2,
        "edge_count": 1,
        "isolated_count": 0,
        "connected_components": 1,
        "entity_type_counts": {"character": 1, "location": 1},
        "rel_type_counts": {"lives_in": 1},
    },
}
GRAPH_SINGLE_NODE_BODY: dict[str, object] = {
    "nodes": [GRAPH_NODE_A],
    "edges": [],
    "stats": {
        "node_count": 1,
        "edge_count": 0,
        "isolated_count": 1,
        "connected_components": 1,
        "entity_type_counts": {"character": 1},
        "rel_type_counts": {},
    },
}
PATH_BODY: dict[str, object] = {
    "path": ["entry-9", "entry-2"],
    "length": 1,
    "entity_names": ["Anna Meyer", "→", "HafenCity"],
}
CANON_ENTRY: dict[str, object] = {
    "id": "entry-1",
    "entity_type": "character",
    "name": "Anna Meyer",
    "slug": "anna-meyer",
    "status": "approved",
    "body": "Kanon-Herkunft.",
    "metadata_": None,
    "tags": None,
    "template_version": None,
    "source": "manual",
    "review_status": "approved",
    "embeddings_dirty": False,
    "last_referenced_at": None,
    "usage_count": 2,
    "created_at": "2026-08-27T00:00:00",
    "updated_at": "2026-08-27T00:00:00",
    "scope": "series",
    "series_id": "series-1",
    "novel_id": None,
    "base_entry_id": None,
}
CANON_LIST_BODY: list[object] = [CANON_ENTRY]
WIKI_INDEX_BODY: dict[str, object] = {
    "novel_id": NOVEL_ID,
    "total_summaries": 2,
    "fresh_count": 1,
    "stale_count": 1,
    "pending_count": 0,
    "last_generated_at": "2026-08-27T00:00:00",
}
WIKI_SUMMARY_A: dict[str, object] = {
    "id": "ws-1",
    "novel_id": NOVEL_ID,
    "entity_id": "entry-9",
    "narrative_summary": "Anna kam aus der HafenCity.",
    "role_in_story": "Protagonistin",
    "key_attributes": ["helmkraut"],
    "relationships": None,
    "chapter_references": None,
    "character_arc": None,
    "status": "FRESH",
    "version": 2,
    "generated_at": "2026-08-27T00:00:00",
    "refreshed_at": None,
}
WIKI_SUMMARY_B: dict[str, object] = {
    **WIKI_SUMMARY_A,
    "id": "ws-2",
    "entity_id": "entry-2",
    "role_in_story": None,
    "status": "STALE",
}
WIKI_LIST_BODY: dict[str, object] = {"items": [WIKI_SUMMARY_A, WIKI_SUMMARY_B], "total": 2}
CHAPTER_SUMMARY_BODY: dict[str, object] = {
    "id": "wcs-1",
    "chapter_id": "chapter-1",
    "narrative_summary": "Anna kam am Hafen an.",
    "key_events": ["Ankunft"],
    "entities_involved": None,
    "themes": None,
    "emotional_arc": None,
    "status": "FRESH",
    "version": 1,
    "generated_at": "2026-08-27T00:00:00",
}
EVENT_BODY: dict[str, object] = ANALYSIS_BODIES["confirmed_event"]
EVENTS_BODY: list[object] = [EVENT_BODY]
AGES_BODY: dict[str, object] = {
    "characters": [
        {
            "character_name": "Anna Meyer",
            "character_id": "entry-9",
            "birth_date": "1990-03-12",
            "birth_date_narrative": "Frühjahr 1990",
            "age_available": True,
        },
        {
            "character_name": "Ben",
            "character_id": None,
            "birth_date": None,
            "birth_date_narrative": None,
            "age_available": False,
        },
    ],
    "characters_with_age": 1,
    "characters_without_age": 1,
}
SUGGESTIONS_BODY: list[object] = [
    {
        "entry_id": "entry-2",
        "entry_type": "location",
        "name": "HafenCity",
        "relevance_score": 0.9,
        "reason": "Aehnlicher Kontext",
        "similarity": 0.8,
        "usage_count": 4,
        "last_referenced_at": None,
    }
]
RESOLVE_BODY: dict[str, object] = {
    "resolved": [
        {
            "mention": "Anna Meyer",
            "entry_id": "entry-9",
            "entry_name": "Anna Meyer",
            "entity_type": "character",
            "slug": "anna-meyer",
        },
        {
            "mention": "Benchmark",
            "entry_id": None,
            "entry_name": None,
            "entity_type": None,
            "slug": None,
        },
    ],
    "html": "<a>Anna Meyer</a> trifft Benchmark.",
}
TEMPLATE_LIST_BODY: list[object] = [
    {
        "entity_type": "character",
        "scope": "user",
        "scope_id": None,
        "schema_version": "2.0.0",
        "based_on_version": None,
        "has_override": False,
        "has_update": True,
    }
]
TEMPLATE_DETAIL_BODY: dict[str, object] = {
    "entity_type": "character",
    "scope": "user",
    "content": "fields:\n  - name",
    "base_content": None,
    "schema_version": "2.0.0",
    "based_on_version": None,
    "is_overridden": False,
}


# ---------------------------------------------------------------------------
# Context plumbing — like in_direction_helpers, plus corpus/chapter_ids
# ---------------------------------------------------------------------------


def timings() -> CapabilityTimings:
    return CapabilityTimings(
        sse_deadline_seconds=5.0, poll_timeout_seconds=5.0, poll_interval_seconds=0.01
    )


def corpus_with(names: tuple[str, ...]) -> Corpus:
    """Corpus whose reference carries the given person names (probe source)."""
    return Corpus(
        stems=(),
        clean=(),
        variants=(),
        reference=Reference(
            persons=tuple(
                Entity(id=f"p{i}", name=name, aliases=(), facts=()) for i, name in enumerate(names)
            ),
            places=(),
            objects=(),
            relations=(),
            events=(),
        ),
        warnings=(),
    )


def context(
    client: BenchmarkClient,
    *,
    corpus: Corpus | None = None,
    chapter_ids: Mapping[str, str] | None = None,
    targets: dict[str, str] | None = None,
    events: list[IngestEvent] | None = None,
) -> CapabilityContext:
    return CapabilityContext(
        client=client,
        corpus=corpus if corpus is not None else corpus_with(()),
        novel_id=NOVEL_ID,
        chapter_ids=dict(chapter_ids) if chapter_ids is not None else {},
        config=timings(),
        events=events if events is not None else [],
        targets=targets if targets is not None else {},
    )


def router(routes: Mapping[str, object]) -> Responder:
    """Method/path-keyed responder: int → 5xx, list/dict → JSON (all OUT is REST)."""

    def respond(_index: int, call: RecordedCall) -> httpx.Response:
        key = f"{call.method} {call.path}"
        if key not in routes:
            raise AssertionError(f"unexpected call: {key}")
        body = routes[key]
        if isinstance(body, int):
            return httpx.Response(body, json={"detail": "boom", "code": "INTERNAL"})
        return httpx.Response(200, json=body)

    return respond


def invoke(
    driver: Callable[[], CapabilityDriver],
    routes: Mapping[str, object],
    *,
    corpus: Corpus | None = None,
    chapter_ids: Mapping[str, str] | None = None,
    targets: dict[str, str] | None = None,
) -> tuple[ScriptedApi, list[IngestEvent], object]:
    """Run one happy-path driver invocation; returns api, sink, parsed."""
    api = ScriptedApi()
    api.respond_with(router(routes))
    events: list[IngestEvent] = []
    result = driver().invoke(
        context(
            make_client(api, access_token="acc-1"),
            corpus=corpus,
            chapter_ids=chapter_ids,
            targets=targets,
            events=events,
        )
    )
    assert result.status is CapabilityStatus.OK, result.reason
    return api, events, result.parsed
