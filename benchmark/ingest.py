"""Build-path ingest drivers — incremental + import corpus ingestion.

Drives the verified novel/chapter/extraction lifecycle (map §4.1-§4.3,
CAP-IN-01) to build a KB from the materialized corpus chapters:

- Fresh novel per run (map §4.1): ``POST /novels`` creates a dedicated
  benchmark novel titled ``KB Benchmark [<variant>/<mode>]``. The setup
  wizard's own novel is deliberately NOT reused: ``complete`` creates one
  (map §3), it is shared across runs/variants, may already carry KB
  entries from earlier runs, and its creation parameters sit outside this
  module's control — only a fresh novel guarantees that scores measure
  exactly this run's ingest (run isolation).
- No publish step (map §4.2): the map documents that NO publish endpoint
  exists — publication state is the ``status`` meta field, and extraction
  reads chapter text directly without requiring ``status=final``. Hence
  no meta PATCH is made; the chapter cycle is create → set content →
  extract → endorse.
- Endorse-all v1 strategy (map §4.3): every extraction candidate is
  mapped to an ``ApplyExtractionItem`` (``confidence`` and
  ``conflict_description`` have no apply-field counterpart) and endorsed
  via ``POST .../kb/extract/apply`` — deterministic, part of the measured
  pipeline, every decision recorded in the event sink (plan Task 6).
- Import mode (map §7 import note): the backend's ``starter="import"``
  creates an empty novel and chapters are delivered via
  ``POST /import/commit`` (ADR-091), so the benchmark's import mode runs
  the identical incremental build path WITHOUT inter-chapter waits; the
  pacing difference itself is part of the measurement (build-time
  comparison incremental vs import).
- Pacing (map §1): extraction is rate-limited under the AI-analysis
  budget (default 5/min), so incremental mode pauses ``PACING_SECONDS``
  on every inter-chapter boundary (injected ``sleeper``; import never
  sleeps).

Fail-fast: the first failing step raises ``IngestError`` (step name,
chapter id, payload-free response summary); the runner (plan Task 15)
decides abort. ``ApiError`` (HTTP-level failures) becomes ``IngestError``;
transport-level errors propagate untouched — a dead stack is not an
ingest-step failure. ``ValueError`` is reserved for caller errors (unknown
mode, empty chapter list) raised BEFORE any HTTP traffic.

Every request/response is appended to the caller-owned ``events`` list as
a sanitized ``IngestEvent`` (``benchmark.ingest_events``) — the Task 14
artifacts consume it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from benchmark.ingest_steps import (
    IngestError,
    create_chapter,
    create_novel,
    endorse_all,
    extract,
    set_content,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from benchmark.client import BenchmarkClient
    from benchmark.corpus_views import Chapter
    from benchmark.ingest_events import IngestEvent

__all__ = [
    "PACING_SECONDS",
    "ChapterIngest",
    "IngestError",
    "IngestResult",
    "ingest",
]

PACING_SECONDS: Final[float] = 12.0
"""Inter-chapter pause (incremental only) — map §1: AI analysis 5/min → 60/5 s."""

_MODES: Final[frozenset[str]] = frozenset({"incremental", "import"})


@dataclass(frozen=True)
class ChapterIngest:
    """Per-chapter outcome: candidate/endorse counts + apply entry ids.

    ``created_entry_ids``/``updated_entry_ids`` are the apply responses'
    entry ids (map §4.3.2 ``ApplyExtractionEntryResult``) — the runner's
    run-target source (plan Task 15, T8 rider: the FIRST created entry
    across chapters becomes ``targets['entry_id']``). The counts remain
    for quick per-chapter comparisons in the raw results.
    """

    stem: str
    chapter_id: str
    candidates: int
    endorsed: int
    created_entries: int
    updated_entries: int
    created_entry_ids: tuple[str, ...]
    updated_entry_ids: tuple[str, ...]


@dataclass(frozen=True)
class IngestResult:
    """Build summary: fresh-novel id + one entry per ingested chapter."""

    novel_id: str
    chapters: tuple[ChapterIngest, ...]


def ingest(
    client: BenchmarkClient,
    chapters: Sequence[Chapter],
    *,
    variant: str,
    mode: str,
    events: list[IngestEvent],
    sleeper: Callable[[float], None] = time.sleep,
) -> IngestResult:
    """Build a fresh benchmark novel's KB from ``chapters`` in order (map §4).

    Caller errors (unknown ``mode``, empty ``chapters``) raise ``ValueError``
    before any HTTP traffic; the first failing step raises ``IngestError``
    (fail-fast — the caller decides abort). Every HTTP exchange is appended
    to ``events`` as a sanitized ``IngestEvent``.
    """
    if mode not in _MODES:
        known = ", ".join(sorted(_MODES))
        raise ValueError(f"unknown ingest mode {mode!r} (known: {known})")
    if not chapters:
        raise ValueError("chapters must be a non-empty sequence of corpus chapters")
    novel_id = create_novel(client, variant=variant, mode=mode, events=events)
    results: list[ChapterIngest] = []
    for index, chapter in enumerate(chapters):
        if index > 0 and mode == "incremental":
            sleeper(PACING_SECONDS)
        results.append(_ingest_chapter(client, novel_id, chapter, events=events))
    return IngestResult(novel_id=novel_id, chapters=tuple(results))


def _ingest_chapter(
    client: BenchmarkClient,
    novel_id: str,
    chapter: Chapter,
    *,
    events: list[IngestEvent],
) -> ChapterIngest:
    """One chapter cycle: create → set content → extract → endorse all."""
    chapter_id = create_chapter(client, novel_id, chapter, events=events)
    set_content(client, novel_id, chapter_id, chapter, events=events)
    candidates = extract(client, novel_id, chapter_id, chapter.stem, events=events)
    created_ids, updated_ids = endorse_all(
        client, novel_id, chapter_id, chapter.stem, candidates, events=events
    )
    return ChapterIngest(
        stem=chapter.stem,
        chapter_id=chapter_id,
        candidates=len(candidates),
        endorsed=len(candidates),
        created_entries=len(created_ids),
        updated_entries=len(updated_ids),
        created_entry_ids=created_ids,
        updated_entry_ids=updated_ids,
    )
