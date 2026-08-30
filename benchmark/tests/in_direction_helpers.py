"""Shared fixture backend for the IN-direction driver tests (Task 8).

Scripted responders + fixture bodies speaking the verified response
shapes (``benchmark/docs/api-surface.md`` §4-§7; per-shape sources are
cited in ``benchmark.drivers.in_records``). Plain helpers — no fixtures,
no network. Split out of the test modules per RULE-04 (file-size limit);
predecessor pattern: ``ingest_helpers.py``/``client_helpers.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from benchmark.corpus_loader import Corpus, Reference
from benchmark.drivers.base import CapabilityContext, CapabilityStatus, CapabilityTimings
from benchmark.tests.client_helpers import (
    SSE_RESPONSE_HEADERS,
    RecordedCall,
    Responder,
    ScriptedApi,
    make_client,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from benchmark.client import BenchmarkClient
    from benchmark.drivers.base import CapabilityDriver
    from benchmark.ingest_events import IngestEvent

NOVEL_ID = "novel-1"
KB = f"/api/v1/novels/{NOVEL_ID}/kb"
TIMELINE = f"/api/v1/planning/timeline/{NOVEL_ID}"

EXTRACT_BODY: dict[str, object] = {
    "results": [
        {
            "item_type": "new_entity",
            "entity_type": "person",
            "name": "Anna Meyer",
            "confidence": 0.97,
            "source_text": "Anna kam aus der HafenCity.",
            "proposed_content": {"description": "Architektin aus Hamburg"},
            "target_entity_id": None,
            "relationship_type": None,
            "related_entity_name": None,
            "conflict_description": None,
        },
        {
            "item_type": "relationship",
            "name": "Anna Meyer",
            "confidence": 0.81,
            "relationship_type": "partner_of",
            "related_entity_name": "Peter Meyer",
            "source_text": "Peter kam abends von einem Hafen.",
            "proposed_content": None,
            "target_entity_id": None,
            "entity_type": None,
            "conflict_description": None,
        },
    ],
    "analysis_notes": "2 Kandidaten",
}
APPLY_BODY: dict[str, object] = {
    "created_entries": [{"id": "entry-9", "name": "Anna Meyer", "entity_type": "person"}],
    "updated_entries": [{"id": "entry-2", "name": "HafenCity", "entity_type": "location"}],
}
SESSION_BODY: dict[str, object] = {
    "id": "session-1",
    "novel_id": NOVEL_ID,
    "entity_type": "character",
    "status": "active",
    "fields": [],
}
IMPROVE_APPLY_BODY: dict[str, object] = {
    "success": True,
    "entry_id": "entry-1",
    "applied_count": 2,
    "message": "2 Verbesserungen angewendet",
}
ANALYSIS_BODIES: dict[str, dict[str, object]] = {
    # Grouped AI-analysis response fixtures (improve / worldbuilding /
    # confirmed timeline event). Grouped — instead of module-level
    # constants — because their schema-faithful score/confidence floats
    # would otherwise trip RULE-18 Pattern 4 (module-level percentage
    # dicts), which checks only top-level assignment dicts; the payload
    # shapes are unchanged.
    "improve": {
        "suggestions": [
            {
                "type": "add_field",
                "target": "description",
                "description": "Herkunft ergaenzen",
                "confidence": 0.8,
                "suggestion_id": 0,
            },
            {
                "type": "expand",
                "target": "body",
                "description": "Beziehungen ausbauen",
                "confidence": 0.6,
                "suggestion_id": 1,
            },
        ],
        "overall_assessment": "solide",
        "completeness_score": 0.5,
    },
    "worldbuilding": {
        "novel_id": NOVEL_ID,
        "entity_count": 4,
        "gap_findings": [{"gap_type": "missing_connection", "description": "Anna unverbunden"}],
        "connection_suggestions": [
            {
                "finding_index": 2,
                "source_entity_id": "e1",
                "source_entity_name": "Anna Meyer",
                "source_entity_type": "character",
                "target_entity_id": "e2",
                "target_entity_name": "HafenCity",
                "target_entity_type": "location",
                "suggested_rel_type": "lives_in",
                "reasoning": "Wohnort im Text",
                "confidence": 0.7,
            }
        ],
        "consistency_issues": [],
        "worldbuilding_score": 0.75,
        "overall_assessment": "ok",
        "summary": {},
        "analyzed_at": "2026-08-27T00:00:00",
    },
    "confirmed_event": {
        "id": "event-1",
        "novel_id": NOVEL_ID,
        "event_name": "Ritt nach Hamburg",
        "description": "",
        "event_type": "plot_point",
        "timestamp_raw": "am dritten Tag",
        "timestamp_normalized": "",
        "temporal_order": None,
        "chapter_id": None,
        "character_refs": [],
        "location_ref": None,
        "causes": "",
        "consequences": "",
        "source": "ai_extraction",
        "confidence": 0.9,
        "is_confirmed": True,
        "created_at": "2026-08-27T00:00:00",
        "updated_at": "2026-08-27T00:00:00",
    },
}
WORLDBUILDING_APPLY_BODY: dict[str, object] = {
    "success": True,
    "created_count": 1,
    "failed_count": 0,
    "errors": [],
}
ENTRY_BODY: dict[str, object] = {
    "id": "entry-9",
    "novel_id": NOVEL_ID,
    "entity_type": "character",
    "name": "Benchmark Figur",
    "slug": "benchmark-figur",
    "status": "draft",
    "tags": None,
    "metadata": None,
    "body": None,
    "template_version": None,
    "source": "benchmark",
    "review_status": "approved",
    "embeddings_dirty": False,
    "created_at": "2026-08-27T00:00:00",
    "updated_at": "2026-08-27T00:00:00",
}
RELATIONSHIP_BODY: dict[str, object] = {
    "id": "rel-1",
    "source_id": "entry-9",
    "target_id": "entry-1",
    "rel_type": "related_to",
    "label": None,
    "direction": "directed",
    "metadata": None,
    "created_at": "2026-08-27T00:00:00",
    "updated_at": "2026-08-27T00:00:00",
    "source_name": None,
    "target_name": None,
}
PREVIEW_BODY: dict[str, object] = {
    "series_id": "series-1",
    "novel_id": NOVEL_ID,
    "canon_empty": True,
    "treatments": [
        {
            "entry_id": "entry-1",
            "slug": "anna-meyer",
            "entity_type": "character",
            "current_scope": "novel",
            "target_scope": "series",
            "reason_code": "CANON_EMPTY",
            "reason": "Canon ist leer, Heuristik aktiv",
        }
    ],
}
JOIN_RESULT_BODY: dict[str, object] = {
    "series_id": "series-1",
    "novel_id": NOVEL_ID,
    "position": 1,
    "promoted_to_canon": 1,
    "kept_as_overlay": 0,
}
SERIES_ENTRY_BODY: dict[str, object] = {
    **ENTRY_BODY,
    "id": "entry-1",
    "scope": "series",
    "series_id": "series-1",
    "novel_id": None,
}
NOVEL_ENTRY_BODY: dict[str, object] = {
    **ENTRY_BODY,
    "id": "entry-1",
    "scope": "novel",
    "novel_id": NOVEL_ID,
    "series_id": "series-1",
}
REFRESH_BODY: dict[str, object] = {
    "summary_id": "ws-1",
    "status": "refreshed",
    "message": "Summary refreshed successfully.",
}
STALE_BODY: dict[str, object] = {"affected_count": 3}
TIMELINE_SSE = (
    b'data: {"id":"ev-1","expression":"am Morgen des dritten Tages",'
    b'"event_name":"Ritt nach Hamburg","timestamp_raw":"am dritten Tag",'
    b'"chapter_reference":"ch-01","character_names":["Anna Meyer"],'
    b'"location_name":"Hamburg","confidence":0.9,"context":"Anna ritt."}\n\n'
    b"data: [DONE]\n\n"
)
TIMELINE_ERROR_SSE = b'data: {"error": "Novel not found", "code": "NOT_FOUND"}\n\ndata: [DONE]\n\n'
VOICE_SSE = (
    b'data: {"event":"progress","progress":"2 Figuren gefunden","is_final":false,'
    b'"x_trace_id":"t-1"}\n\n'
    b'data: {"event":"result","result":{"character_name":"Anna Meyer",'
    b'"voice_analysis":{"style":"nuchtern"},"distinctiveness_notes":"knapper Stil",'
    b'"kb_entry_id":"entry-1"},"is_final":false}\n\n'
    b'data: {"event":"done","is_final":true}\n\ndata: [DONE]\n\n'
)
VOICE_ERROR_SSE = (
    b'data: {"event":"error","error":"Character-voice analysis failed.",'
    b'"is_final":true}\n\ndata: [DONE]\n\n'
)


def timings() -> CapabilityTimings:
    return CapabilityTimings(
        sse_deadline_seconds=5.0, poll_timeout_seconds=5.0, poll_interval_seconds=0.01
    )


def empty_corpus() -> Corpus:
    return Corpus(
        stems=(),
        clean=(),
        variants=(),
        reference=Reference(persons=(), places=(), objects=(), relations=(), events=()),
        warnings=(),
    )


def context(
    client: BenchmarkClient,
    *,
    targets: dict[str, str] | None = None,
    events: list[IngestEvent] | None = None,
) -> CapabilityContext:
    return CapabilityContext(
        client=client,
        corpus=empty_corpus(),
        novel_id=NOVEL_ID,
        chapter_ids={},
        config=timings(),
        events=events if events is not None else [],
        targets=targets if targets is not None else {},
    )


def router(routes: Mapping[str, object]) -> Responder:
    """Method/path-keyed responder: bytes → SSE stream, int → 5xx, dict → JSON."""

    def respond(_index: int, call: RecordedCall) -> httpx.Response:
        key = f"{call.method} {call.path}"
        if key not in routes:
            raise AssertionError(f"unexpected call: {key}")
        body = routes[key]
        if isinstance(body, bytes):
            return httpx.Response(200, headers=SSE_RESPONSE_HEADERS, content=body)
        if isinstance(body, int):
            return httpx.Response(body, json={"detail": "boom", "code": "INTERNAL"})
        return httpx.Response(200, json=body)

    return respond


def invoke(
    driver: Callable[[], CapabilityDriver],
    routes: Mapping[str, object],
    *,
    targets: dict[str, str] | None = None,
) -> tuple[ScriptedApi, list[IngestEvent], object]:
    """Run one happy-path driver invocation; returns api, sink, parsed."""
    api = ScriptedApi()
    api.respond_with(router(routes))
    events: list[IngestEvent] = []
    result = driver().invoke(
        context(make_client(api, access_token="acc-1"), targets=targets, events=events)
    )
    assert result.status is CapabilityStatus.OK, result.reason
    return api, events, result.parsed
