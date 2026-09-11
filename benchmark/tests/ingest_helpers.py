"""Shared build-path fixture backend for the ingest driver tests.

Scripted MockTransport responder speaking the verified CAP-IN-01 shapes
(``benchmark/docs/api-surface.md`` §4) plus the ``run_ingest`` helper that
wires a pre-authenticated client (``tokens`` constructor DI — a scripted
login would pollute the pinned call sequences and the event sink).
Plain helpers — no fixtures, no network. Sequence truth: map §4.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import httpx

from benchmark.corpus_views import parse_chapter
from benchmark.ingest import ingest
from benchmark.tests.client_helpers import (
    RecordedCall,
    Responder,
    ScriptedApi,
    make_client,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from benchmark.corpus_views import Chapter
    from benchmark.ingest import IngestResult
    from benchmark.ingest_events import IngestEvent

NOVELS_PATH: Final[str] = "/api/v1/novels"
NOVEL_ID: Final[str] = "novel-1"
VARIANT: Final[str] = "light"

CHAPTERS: Final[tuple[Chapter, ...]] = (
    parse_chapter("ch-01", "# Kapitel Eins\n\n" + "Wort " * 40),
    parse_chapter("ch-02", "# Kapitel Zwei\n\n" + "Satz " * 30),
)

CANDIDATES: Final[tuple[dict[str, object], ...]] = (
    {
        "item_type": "new_entity",
        "entity_type": "person",
        "name": "Anna Meyer",
        "confidence": 0.97,
        "source_text": "Anna kam aus der HafenCity.",
        "proposed_content": {"description": "Architektin aus Hamburg"},
    },
    {
        "item_type": "relationship",
        "name": "Anna Meyer",
        "confidence": 0.81,
        "relationship_type": "partner_of",
        "related_entity_name": "Peter Meyer",
        "source_text": "Peter kam abends von einem Hafen.",
    },
    {
        "item_type": "conflict",
        "name": "Geburtsjahr Peter",
        "confidence": 0.42,
        "conflict_description": "Widersprechende Jahreszahlen",
        "source_text": "Acht Ordner pro Kaimauer.",
    },
)


def chapter_id(index: int) -> str:
    return f"chapter-{index + 1}"


def chapters_path() -> str:
    return f"/api/v1/novels/{NOVEL_ID}/chapters"


def content_path(index: int) -> str:
    return f"{chapters_path()}/{chapter_id(index)}/content"


def extract_path(index: int) -> str:
    return f"/api/v1/novels/{NOVEL_ID}/kb/extract/{chapter_id(index)}"


def apply_path() -> str:
    return f"/api/v1/novels/{NOVEL_ID}/kb/extract/apply"


def ingest_responder(
    *,
    novel_status: int = 201,
    extract_status: int = 200,
    extract_body: dict[str, object] | None = None,
    apply_status: int = 200,
    leak: dict[str, object] | None = None,
) -> Responder:
    """Build-path backend: one novel, sequential chapter ids, CAP-IN-01 shapes."""
    created: list[str] = []

    def respond(_index: int, call: RecordedCall) -> httpx.Response:
        if call.method == "POST" and call.path == NOVELS_PATH:
            if novel_status >= 400:
                return httpx.Response(
                    novel_status, json={"detail": "novel rejected", "code": "CONFLICT"}
                )
            return httpx.Response(201, json={"id": NOVEL_ID, "title": "KB Benchmark"})
        if call.method == "POST" and call.path == chapters_path():
            created.append(chapter_id(len(created)))
            return httpx.Response(201, json={"id": created[-1]})
        if call.method == "PUT" and call.path.endswith("/content"):
            return httpx.Response(200, json={"id": "ignored"})
        if call.method == "POST" and call.path.endswith("/kb/extract/apply"):
            if apply_status >= 400:
                return httpx.Response(
                    apply_status, json={"detail": "apply rejected", "code": "INVALID"}
                )
            return httpx.Response(
                200,
                json={
                    "created_entries": [
                        {"id": "entry-1", "name": "Anna Meyer", "entity_type": "person"}
                    ],
                    "updated_entries": [],
                },
            )
        if call.method == "POST" and "/kb/extract/" in call.path:
            if extract_status >= 400:
                body = extract_body if extract_body is not None else {"detail": "extract failed"}
                return httpx.Response(extract_status, json=body)
            payload: dict[str, object] = (
                extract_body if extract_body is not None else {"results": list(CANDIDATES)}
            )
            if "analysis_notes" not in payload:
                payload = {**payload, "analysis_notes": "ok"}
            if leak is not None:
                payload = {**payload, **leak}
            return httpx.Response(200, json=payload)
        raise AssertionError(f"unexpected call: {call.method} {call.path}")

    return respond


def run_ingest(
    mode: str,
    responder: Responder | None = None,
    sleeper: Callable[[float], None] | None = None,
    chapters: tuple[Chapter, ...] = CHAPTERS,
    variant: str = VARIANT,
) -> tuple[ScriptedApi, list[IngestEvent], IngestResult]:
    """Run ``ingest`` against a scripted backend; returns api, sink, result.

    ``responder`` defaults to the standard build-path backend.
    """
    api = ScriptedApi()
    api.respond_with(responder if responder is not None else ingest_responder())
    client = make_client(api, access_token="acc-1")
    events: list[IngestEvent] = []
    result = ingest(
        client,
        chapters,
        variant=variant,
        mode=mode,
        events=events,
        sleeper=sleeper if sleeper is not None else lambda _seconds: None,
    )
    return api, events, result
