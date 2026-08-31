"""Build-path step calls — one lifecycle step per function, shape-checked.

Each function drives exactly one verified endpoint exchange (map §4.1-§4.3)
through the authenticated client, records its sanitized raw event into the
caller-owned sink, and narrows the response to what the next step consumes;
a shape violation raises ``IngestError`` (fail-fast — the runner decides
abort). HTTP-level failures (``ApiError``) become ``IngestError`` AFTER the
failed exchange is recorded, so the artifact sink always carries the
terminal event.

Summary discipline: error summaries are payload-free (status codes, paths,
field names, server-provided text only — provision.py precedent); request
bodies are never rendered into messages.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Final, cast

from benchmark.client import ApiError
from benchmark.ingest_events import record

if TYPE_CHECKING:
    import httpx

    from benchmark.client import BenchmarkClient
    from benchmark.corpus_views import Chapter
    from benchmark.ingest_events import IngestEvent

_NOVELS_PATH: Final[str] = "/api/v1/novels"

_APPLY_FIELDS: Final[tuple[str, ...]] = (
    "item_type",
    "name",
    "entity_type",
    "proposed_content",
    "target_entity_id",
    "relationship_type",
    "related_entity_name",
    "source_text",
)
"""``ApplyExtractionItem`` fields copied from candidates (map §4.3.2); the
ExtractionItem-only fields ``confidence``/``conflict_description`` are dropped."""


class IngestError(RuntimeError):
    """One build-path step failed — fail-fast signal to the runner (Task 15).

    ``summary`` is payload-free and safe to log or embed in artifacts.
    """

    def __init__(self, *, step: str, chapter_id: str | None, summary: str) -> None:
        self.step = step
        self.chapter_id = chapter_id
        self.summary = summary
        location = f" for chapter {chapter_id!r}" if chapter_id is not None else ""
        super().__init__(f"ingest step {step!r} failed{location}: {summary}")


def _call(
    client: BenchmarkClient,
    events: list[IngestEvent],
    *,
    step: str,
    chapter_stem: str | None,
    chapter_id: str | None,
    method: str,
    path: str,
    request_body: object | None = None,
) -> object:
    """Run one authenticated call, record its sanitized event, fail fast.

    Returns the parsed JSON body. No mapped endpoint returns a bare JSON
    string scalar (map §4), so a ``str`` body means the 2xx response was
    not JSON — recorded, then rejected as a shape violation.
    """
    started = time.perf_counter()
    try:
        response = client.request(method, path, json=request_body)
    except ApiError as error:
        record(
            events,
            step=step,
            chapter_stem=chapter_stem,
            method=method,
            path=path,
            status=error.status,
            started=started,
            request_body=request_body,
            response_body=error.body,
        )
        raise IngestError(step=step, chapter_id=chapter_id, summary=str(error)) from error
    body = _json_body(response)
    record(
        events,
        step=step,
        chapter_stem=chapter_stem,
        method=method,
        path=path,
        status=response.status_code,
        started=started,
        request_body=request_body,
        response_body=body,
    )
    if isinstance(body, str):
        raise IngestError(
            step=step,
            chapter_id=chapter_id,
            summary=f"{path}: 2xx response body is not JSON",
        )
    return body


def _json_body(response: httpx.Response) -> object:
    """Parsed JSON body; a non-JSON body falls back to raw text (flagged)."""
    try:
        return response.json()
    except ValueError:
        return response.text


def create_novel(
    client: BenchmarkClient,
    *,
    variant: str,
    mode: str,
    events: list[IngestEvent],
) -> str:
    """``POST /novels`` — fresh, run-scoped isolation novel (map §4.1.2)."""
    payload: dict[str, object] = {
        "title": f"KB Benchmark [{variant}/{mode}]",
        "author": "",
        "genre": "",
        "writing_language": "de",  # the corpus is German (plan global constraints)
        "tone": "",
        "story_structure": "three_act",
        "logline": "",
        "synopsis": "",
    }
    body = _call(
        client,
        events,
        step="create_novel",
        chapter_stem=None,
        chapter_id=None,
        method="POST",
        path=_NOVELS_PATH,
        request_body=payload,
    )
    return _require_id(body, step="create_novel", chapter_id=None, label="novel")


def _chapters_path(novel_id: str) -> str:
    """Chapter collection path under the run's novel (map §4.2 prefix)."""
    return f"/api/v1/novels/{novel_id}/chapters"


def create_chapter(
    client: BenchmarkClient,
    novel_id: str,
    chapter: Chapter,
    *,
    events: list[IngestEvent],
) -> str:
    """``POST .../chapters`` — empty shell; content arrives via PUT (map §4.2)."""
    payload: dict[str, object] = {
        "title": chapter.title if chapter.title is not None else chapter.stem,
        "content": "",
        "position": None,  # appended in corpus order
        "volume_id": None,
    }
    body = _call(
        client,
        events,
        step="create_chapter",
        chapter_stem=chapter.stem,
        chapter_id=None,
        method="POST",
        path=_chapters_path(novel_id),
        request_body=payload,
    )
    return _require_id(body, step="create_chapter", chapter_id=None, label="chapter")


def set_content(
    client: BenchmarkClient,
    novel_id: str,
    chapter_id: str,
    chapter: Chapter,
    *,
    events: list[IngestEvent],
) -> None:
    """``PUT .../content`` — full chapter text; the server recomputes words."""
    _call(
        client,
        events,
        step="set_content",
        chapter_stem=chapter.stem,
        chapter_id=chapter_id,
        method="PUT",
        path=f"{_chapters_path(novel_id)}/{chapter_id}/content",
        request_body={"content": chapter.text, "word_count": None},
    )


def extract(
    client: BenchmarkClient,
    novel_id: str,
    chapter_id: str,
    stem: str,
    *,
    events: list[IngestEvent],
) -> list[dict[str, object]]:
    """``POST .../kb/extract/{chapter_id}`` — CAP-IN-01 trigger (map §4.3.1)."""
    body = _call(
        client,
        events,
        step="extract",
        chapter_stem=stem,
        chapter_id=chapter_id,
        method="POST",
        path=f"/api/v1/novels/{novel_id}/kb/extract/{chapter_id}",
    )
    if not isinstance(body, dict):
        raise IngestError(
            step="extract", chapter_id=chapter_id, summary="extract: response is not a JSON object"
        )
    entry = cast("dict[str, object]", body)
    results = entry.get("results")
    if not isinstance(results, list):
        raise IngestError(
            step="extract",
            chapter_id=chapter_id,
            summary=f"extract: 'results' must be a list, got {type(results).__name__}",
        )
    return [_candidate(item, chapter_id) for item in cast("list[object]", results)]


def _candidate(item: object, chapter_id: str) -> dict[str, object]:
    """Shape-check one extraction candidate (map §4.3.1 ExtractionItem)."""
    if not isinstance(item, dict):
        raise IngestError(
            step="extract",
            chapter_id=chapter_id,
            summary="extract: candidate is not a JSON object",
        )
    candidate = cast("dict[str, object]", item)
    if not isinstance(candidate.get("item_type"), str) or not isinstance(
        candidate.get("name"), str
    ):
        raise IngestError(
            step="extract",
            chapter_id=chapter_id,
            summary="extract: candidate missing string 'item_type'/'name'",
        )
    return candidate


def endorse_all(
    client: BenchmarkClient,
    novel_id: str,
    chapter_id: str,
    stem: str,
    candidates: list[dict[str, object]],
    *,
    events: list[IngestEvent],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``POST .../kb/extract/apply`` with EVERY candidate endorsed (map §4.3.2).

    v1 strategy: endorse all, deterministically — the strategy is part of
    the measured pipeline (plan Task 6). The candidate→apply mapping drops
    the ExtractionItem-only fields; rejection = omission has no role here.
    Returns the apply responses' entry ids (created, updated) — the T8
    rider's run-target source (``runner_targets``).
    """
    items = [
        {field: candidate[field] for field in _APPLY_FIELDS if field in candidate}
        for candidate in candidates
    ]
    body = _call(
        client,
        events,
        step="endorse",
        chapter_stem=stem,
        chapter_id=chapter_id,
        method="POST",
        path=f"/api/v1/novels/{novel_id}/kb/extract/apply",
        request_body={"items": items},
    )
    return _entry_ids(body, chapter_id)


def _entry_ids(body: object, chapter_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Read the ``created_entries``/``updated_entries`` entry ids (map §4.3.2)."""
    if not isinstance(body, dict):
        raise IngestError(
            step="endorse", chapter_id=chapter_id, summary="apply: response is not a JSON object"
        )
    entry = cast("dict[str, object]", body)
    return (
        _ids_of(entry.get("created_entries"), "created_entries", chapter_id),
        _ids_of(entry.get("updated_entries"), "updated_entries", chapter_id),
    )


def _ids_of(value: object, label: str, chapter_id: str) -> tuple[str, ...]:
    """Entry-id list of one apply bucket (``ApplyExtractionEntryResult``)."""
    if not isinstance(value, list):
        raise IngestError(
            step="endorse",
            chapter_id=chapter_id,
            summary=f"apply: {label!r} must be a list, got {type(value).__name__}",
        )
    ids: list[str] = []
    for item in cast("list[object]", value):
        if not isinstance(item, dict):
            raise IngestError(
                step="endorse",
                chapter_id=chapter_id,
                summary=f"apply: {label} entry is not a JSON object",
            )
        entry = cast("dict[str, object]", item)
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise IngestError(
                step="endorse",
                chapter_id=chapter_id,
                summary=f"apply: {label} entry missing non-empty string 'id'",
            )
        ids.append(identifier)
    return tuple(ids)


def _require_id(body: object, *, step: str, chapter_id: str | None, label: str) -> str:
    """Extract the non-empty string ``id`` a 201 creation response must carry."""
    if not isinstance(body, dict):
        raise IngestError(
            step=step, chapter_id=chapter_id, summary=f"{label}: response is not a JSON object"
        )
    entry = cast("dict[str, object]", body)
    identifier = entry.get("id")
    if not isinstance(identifier, str) or not identifier:
        raise IngestError(
            step=step,
            chapter_id=chapter_id,
            summary=f"{label}: response missing non-empty string 'id'",
        )
    return identifier
