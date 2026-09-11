"""Shared fixture backend for the CHECK-direction driver tests (Task 10).

Scripted responders + fixture bodies speaking the verified response shapes
(``benchmark/docs/api-surface.md`` §6-§7; per-shape schema sources are cited
in ``benchmark.drivers.check_records``). Plain helpers — no fixtures, no
network. Split out of the test modules per RULE-04 (predecessor pattern:
``in_direction_helpers.py`` / ``out_direction_helpers.py``). Score-bearing
REST bodies are grouped under ``CHECK_BODIES`` (``ANALYSIS_BODIES``
precedent: module-level percentage dicts would trip RULE-18 Pattern 4);
SSE streams are byte constants.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

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
from benchmark.tests.in_direction_helpers import KB, NOVEL_ID

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from benchmark.client import BenchmarkClient
    from benchmark.drivers.base import CapabilityDriver
    from benchmark.ingest_events import IngestEvent

# ---------------------------------------------------------------------------
# Path constants (registry EndpointSpec templates, /api/v1-joined)
# ---------------------------------------------------------------------------

CHK_CHECK: Final[str] = f"{KB}/consistency-check"
SERIES_ID: Final[str] = "series-1"
SERIES_CONSISTENCY: Final[str] = f"/api/v1/series/{SERIES_ID}/consistency/check"
SERIES_SNAPSHOT: Final[str] = f"/api/v1/series/{SERIES_ID}/consistency/{NOVEL_ID}"
SERIES_VOICE_DRIFT: Final[str] = f"/api/v1/series/{SERIES_ID}/voice-drift/check"
TEMPORAL: Final[str] = f"/api/v1/planning/timeline/{NOVEL_ID}/consistency"
CHAPTER_ID: Final[str] = "chapter-1"
VOICE_CHECK: Final[str] = f"/api/v1/analysis/voice-check/{CHAPTER_ID}"
VOICE_DRIFT: Final[str] = f"/api/v1/analysis/voice-drift/{NOVEL_ID}"
AUTHOR_DRIFT: Final[str] = f"/api/v1/analysis/author-voice-drift/{NOVEL_ID}"

# ---------------------------------------------------------------------------
# Fixture bodies — schema-faithful per the cited response schemas
# ---------------------------------------------------------------------------

CHECK_BODIES: Final[dict[str, dict[str, object]]] = {
    # ConsistencyCheckResponse (kb/consistency_contracts.py) with two
    # ConsistencyIssue findings (entry-internal LLM + algorithmic asymmetry).
    "consistency": {
        "novel_id": NOVEL_ID,
        "entity_count": 3,
        "issues": [
            {
                "finding_index": 0,
                "category": "entry_internal",
                "entity_ids": ["entry-9"],
                "entity_names": ["Anna Meyer"],
                "description": "Widerspruechliche Felder im Eintrag.",
                "contradiction": "Geburtsjahr 1990 widerspricht 1985.",
                "suggested_resolution": None,
                "severity": "major",
                "confidence": 0.9,
            },
            {
                "finding_index": 1,
                "category": "relationship_asymmetry",
                "entity_ids": ["entry-9", "entry-2"],
                "entity_names": ["Anna Meyer", "HafenCity"],
                "description": "Reziproke Beziehung fehlt.",
                "contradiction": "lives_in ohne inhabited_by.",
                "suggested_resolution": "Inverse Beziehung ergaenzen.",
                "severity": "minor",
                "confidence": 1.0,
            },
        ],
        "summary": {"entry_internal": 1, "asymmetry": 1, "cross_entity": 0},
        "suppressed_count": 2,
        "checked_at": "2026-08-27T00:00:00",
    },
    # SeriesConsistencyCheckResponse (series/series_consistency_schemas.py)
    # with two CanonConflict findings (error + warning), Core type verbatim.
    "series_consistency": {
        "series_id": SERIES_ID,
        "novel_id": NOVEL_ID,
        "conflicts": [
            {
                "canon_entry_slug": "character-anna-herkunft",
                "canon_entry_name": "Anna — Herkunft",
                "chapter_text_excerpt": "Anna kam aus Berlin.",
                "canon_statement": "Anna kommt aus Hamburg.",
                "explanation": "Beide Aussagen koennen nicht gleichzeitig gelten.",
                "severity": "error",
            },
            {
                "canon_entry_slug": "location-hafen-lage",
                "canon_entry_name": "Hafen — Lage",
                "chapter_text_excerpt": "Der Hafen lag suedlich.",
                "canon_statement": "Der Hafen liegt noerdlich.",
                "explanation": "Moeglicher Widerspruch.",
                "severity": "warning",
            },
        ],
        "summary": "Zwei Widersprueche gefunden.",
        "canon_entry_count": 5,
        "chapter_count": 2,
    },
    # AuthorVoiceDriftResponse (analysis/schemas_author_voice_drift.py,
    # reused verbatim by the series voice-drift router) with a full result.
    "series_voice_drift": {
        "novel_id": NOVEL_ID,
        "result": {
            "novel_id": NOVEL_ID,
            "trend": [
                {
                    "chapter_id": CHAPTER_ID,
                    "match_subscore": 88.0,
                    "per_metric_deltas": {"avg_sentence_length": 0.12},
                    "band": "stable",
                },
                {
                    "chapter_id": "chapter-2",
                    "match_subscore": 61.0,
                    "per_metric_deltas": {},
                    "band": "moderate",
                },
            ],
            "jumps": [
                {
                    "from_chapter_id": CHAPTER_ID,
                    "to_chapter_id": "chapter-2",
                    "jumped_metrics": ["avg_sentence_length"],
                    "magnitude": 0.4,
                }
            ],
            "overall_match_score": 74.5,
            "overall_band": "minor",
            "drift": {
                "drift_type": "inconsistency",
                "confidence": 0.8,
                "longitudinal_reasons": ["Sprung in der Satzlaenge"],
                "per_chapter_notes": [
                    {"chapter_id": "chapter-2", "note": "Deutlich kuerzere Saetze."}
                ],
                "suggested_attention": ["chapter-2"],
            },
        },
        "no_profile": None,
    },
    # AuthorVoiceDriftResponse graceful skip (no series voice profile).
    "series_voice_no_profile": {
        "novel_id": NOVEL_ID,
        "result": None,
        "no_profile": {"reason": "no_stored_profile"},
    },
    # TemporalConsistencyResponse (planning/timeline_schemas.py) — one
    # deterministic duration issue + one LLM warning.
    "temporal": {
        "issues": [
            {
                "severity": "error",
                "rule_id": "duration_impossibility",
                "event_ids": ["event-1", "event-2"],
                "description": "Unmoegliche Dauer zwischen den Ereignissen.",
                "suggestion": "Zeitangaben der Ereignisse anpassen.",
                "source": "deterministic",
            },
            {
                "severity": "warning",
                "rule_id": "llm_validation",
                "event_ids": ["event-3"],
                "description": "Zeitliche Einordnung unklar.",
                "suggestion": "Ereignis pruefen.",
                "source": "llm",
            },
        ],
        "deterministic_pass": False,
        "overall_assessment": "Zwei Probleme gefunden.",
    },
}

# SeriesDriftSnapshotResponse (series/series_drift_schemas.py) — the GET
# body for CAP-CHK-02; embedded section docs kept schema-faithful but
# minimal (the driver projects only generated_at/stale/presence flags).
CHECK_BODIES["series_snapshot"] = {
    "series_id": SERIES_ID,
    "novel_id": NOVEL_ID,
    "generated_at": "2026-08-27T00:00:00",
    "stale": False,
    "consistency": {
        "series_id": SERIES_ID,
        "novel_id": NOVEL_ID,
        "conflicts": [],
        "summary": "Keine Widersprueche.",
        "canon_entry_count": 5,
        "chapter_count": 2,
    },
    "voice_drift": {"novel_id": NOVEL_ID, "result": None, "no_profile": None},
}

# ---------------------------------------------------------------------------
# SSE streams — flavor B (map §6); byte constants, not dicts
# ---------------------------------------------------------------------------

VOICE_CHECK_SSE: Final[bytes] = (
    b'data: {"event":"progress","progress":"Stimmen werden geprueft","is_final":false}\n\n'
    b'data: {"event":"result","result":{"character_name":"Anna Meyer",'
    b'"match_score":42.0,"band":"red","match_judgment":"off",'
    b'"qualitative_sub_score":40.0,"metric_delta_subscore":44.0,'
    b'"flagged_lines":[{"quote":"Na.","reason":"Zu knapp fuer die gespeicherte Stimme."}],'
    b'"has_profile":true,"n_comparable_metrics":3},"is_final":false}\n\n'
    b'data: {"event":"result","result":{"character_name":"Ben","match_score":null,'
    b'"band":null,"match_judgment":null,"qualitative_sub_score":null,'
    b'"metric_delta_subscore":null,"flagged_lines":[],"has_profile":false,'
    b'"n_comparable_metrics":0},"is_final":false}\n\n'
    b'data: {"event":"done","is_final":true}\n\ndata: [DONE]\n\n'
)
VOICE_CHECK_ERROR_SSE: Final[bytes] = (
    b'data: {"event":"error","error":"Voice-check analysis failed.","is_final":true}\n\n'
    b"data: [DONE]\n\n"
)
VOICE_DRIFT_SSE: Final[bytes] = (
    b'data: {"event":"progress","progress":"2 Charaktere","is_final":false}\n\n'
    b'data: {"event":"character_result","result":{"character_id":"entry-9",'
    b'"character_name":"Anna Meyer","trend":[{"chapter_id":"chapter-1",'
    b'"match_subscore":88.0,"per_metric_deltas":{"avg_sentence_length":0.12},'
    b'"band":"stable"},{"chapter_id":"chapter-2","match_subscore":61.0,'
    b'"per_metric_deltas":{},"band":"moderate"}],"jumps":[{"from_chapter_id":'
    b'"chapter-1","to_chapter_id":"chapter-2","jumped_metrics":'
    b'["avg_sentence_length"],"magnitude":0.4}],"overall_match_score":74.5,'
    b'"overall_band":"minor","drift":{"drift_type":"inconsistency",'
    b'"confidence":0.8,"longitudinal_reasons":["Sprung in der Satzlaenge"],'
    b'"per_chapter_notes":[{"chapter_id":"chapter-2","note":"Deutlich '
    b'kuerzere Saetze."}],"suggested_attention":["chapter-2"]}},"is_final":false}\n\n'
    b'data: {"event":"no_profile","no_profile":{"character_id":"",'
    b'"character_name":"Ben","reason":"no_stored_profile"},"is_final":false}\n\n'
    b'data: {"event":"done","is_final":true}\n\ndata: [DONE]\n\n'
)
VOICE_DRIFT_ERROR_SSE: Final[bytes] = (
    b'data: {"event":"error","error":"Voice-drift analysis failed.","is_final":true}\n\n'
    b"data: [DONE]\n\n"
)
VOICE_DRIFT_UNKNOWN_SSE: Final[bytes] = (
    b'data: {"event":"mystery","is_final":false}\n\n'
    b'data: {"event":"done","is_final":true}\n\ndata: [DONE]\n\n'
)
AUTHOR_DRIFT_SSE: Final[bytes] = (
    b'data: {"event":"progress","progress":"2 Kapitel","is_final":false}\n\n'
    b'data: {"event":"result","result":{"novel_id":"' + NOVEL_ID.encode() + b'",'
    b'"trend":[{"chapter_id":"chapter-1","match_subscore":90.0,'
    b'"per_metric_deltas":{},"band":"stable"}],"jumps":[],'
    b'"overall_match_score":90.0,"overall_band":"stable","drift":'
    b'{"drift_type":"evolution","confidence":0.6,"longitudinal_reasons":[],'
    b'"per_chapter_notes":[],"suggested_attention":[]}},"is_final":false}\n\n'
    b'data: {"event":"done","is_final":true}\n\ndata: [DONE]\n\n'
)
AUTHOR_DRIFT_NO_PROFILE_SSE: Final[bytes] = (
    b'data: {"event":"no_profile","no_profile":{"reason":"no_stored_profile"},'
    b'"is_final":false}\n\n'
    b'data: {"event":"done","is_final":true}\n\ndata: [DONE]\n\n'
)
AUTHOR_DRIFT_CONFLICTING_SSE: Final[bytes] = (
    b'data: {"event":"result","result":{"novel_id":"' + NOVEL_ID.encode() + b'",'
    b'"trend":[],"jumps":[],"overall_match_score":null,"overall_band":null,'
    b'"drift":{"drift_type":"evolution","confidence":0.0,'
    b'"longitudinal_reasons":[],"per_chapter_notes":[],'
    b'"suggested_attention":[]}},"is_final":false}\n\n'
    b'data: {"event":"no_profile","no_profile":{"reason":"no_stored_profile"},'
    b'"is_final":false}\n\ndata: {"event":"done","is_final":true}\n\n'
    b"data: [DONE]\n\n"
)
AUTHOR_DRIFT_ERROR_SSE: Final[bytes] = (
    b'data: {"event":"error","error":"Author-voice-drift analysis failed.",'
    b'"is_final":true}\n\ndata: [DONE]\n\n'
)

# ---------------------------------------------------------------------------
# Context plumbing — like the T8/T9 helper modules
# ---------------------------------------------------------------------------


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
