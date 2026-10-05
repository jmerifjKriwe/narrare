"""Bulk extraction contracts — Protocols BEFORE implementation (RULE-03, ADR-092).

The service consumes four seams (store/reader/dispatcher via the service,
pacer via the runner); unit tests substitute Protocol-conformant fakes.
Protocol constants (engine cap, TTL) and the NORMATIVE STATE ENUMS (spec
§4.1/§4.2) live here so schemas and registry share one definition — the
enums moved from ``schemas.py`` in F3 T2 because that file sat exactly at
its RULE-04 hard limit and the enums are contract vocabulary ("normative
set"); ``schemas.py`` re-exports them so the import seam is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.kb.bulk_extraction.schemas import (
        BulkExtractionJobView,
        BulkExtractionResultsView,
        BulkExtractionStatusView,
    )

#: Engine cap — protocol constant (like the v1 import guardrails), no settings
#: surface (RULE-18b). 422 names the count when exceeded.
BULK_EXTRACT_MAX_CHAPTERS: Final[int] = 200

#: Terminal jobs are swept from the in-memory registry after this TTL.
BULK_JOB_TTL: Final[timedelta] = timedelta(hours=24)


class BulkChapterState(StrEnum):
    """Per-chapter state inside a bulk job (spec §4.2 — normative set)."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class BulkJobStatus(StrEnum):
    """Job-level lifecycle status (spec §4.1 — normative set)."""

    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


#: Job kind discriminator (F3 §3): ``corpus`` marks jobs that arm the
#: automatic post-pass ADR-085 dedup analysis; ``explicit`` never triggers it.
BulkJobKind = Literal["explicit", "corpus"]


@dataclass(frozen=True, slots=True)
class BulkChapterRef:
    """Identity slice of one chapter the job will process (position order)."""

    chapter_id: UUID
    title: str
    position: int


@dataclass(frozen=True, slots=True)
class CorpusChapterRow(BulkChapterRef):
    """Corpus enumeration unit: :class:`BulkChapterRef` + word count.

    The corpus pass (F3, spec §4) enumerates the whole novel in ``position``
    order and needs each chapter's word count for the D20a cap math; the
    explicit-ids engine path (:class:`BulkChapterRef`) stays word-agnostic.
    """

    word_count: int


@runtime_checkable
class BulkChapterReader(Protocol):
    """Load + validate chapters for a novel (raises ValidationError on bad ids)."""

    async def load(self, novel_id: UUID, chapter_ids: Sequence[UUID]) -> list[BulkChapterRef]: ...


@runtime_checkable
class CorpusChapterSource(Protocol):
    """Enumerate ALL chapters of a novel in ``position`` order with word counts.

    Backed by ``ChapterRepository.list_by_novel`` (T2 wires it); the corpus
    scope module consumes the rows purely. Raises ``NotFoundError`` for
    unknown/foreign novels (owner gate happens in the service first).
    """

    async def load_all(self, novel_id: UUID) -> list[CorpusChapterRow]: ...


@runtime_checkable
class BulkExtractionPacer(Protocol):
    """Acquire one shared-analysis-budget slot (never blocks the event loop)."""

    async def acquire(self) -> None: ...


@runtime_checkable
class BulkExtractionDispatcher(Protocol):
    """Launch the in-process runner for a job (fire-and-forget)."""

    async def dispatch(self, job_id: str, novel_id: UUID, owner_id: UUID) -> None: ...


@runtime_checkable
class BulkExtractionJobStore(Protocol):
    """Registry operations consumed by the service (T2 implements)."""

    async def create_job(
        self,
        novel_id: UUID,
        owner_user_id: UUID,
        chapters: Sequence[BulkChapterRef],
        kind: BulkJobKind = "explicit",
    ) -> BulkExtractionJobView: ...

    async def get_status(self, job_id: str, user_id: UUID) -> BulkExtractionStatusView: ...

    async def get_results(self, job_id: str, user_id: UUID) -> BulkExtractionResultsView: ...

    async def cancel_job(self, job_id: str, user_id: UUID) -> BulkExtractionJobView: ...

    async def resume_job(self, job_id: str, user_id: UUID) -> BulkExtractionJobView: ...

    async def has_active_for(self, novel_id: UUID) -> bool: ...


__all__ = [
    "BULK_EXTRACT_MAX_CHAPTERS",
    "BULK_JOB_TTL",
    "BulkChapterReader",
    "BulkChapterRef",
    "BulkChapterState",
    "BulkExtractionDispatcher",
    "BulkExtractionJobStore",
    "BulkExtractionPacer",
    "BulkJobKind",
    "BulkJobStatus",
    "CorpusChapterRow",
    "CorpusChapterSource",
]
