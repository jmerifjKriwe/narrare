"""Bulk extraction contracts — Protocols BEFORE implementation (RULE-03, ADR-092).

The service consumes four seams (store/reader/dispatcher via the service,
pacer via the runner); unit tests substitute Protocol-conformant fakes.
Protocol constants (engine cap, TTL) live here so schemas and registry share
one definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

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


@dataclass(frozen=True, slots=True)
class BulkChapterRef:
    """Identity slice of one chapter the job will process (position order)."""

    chapter_id: UUID
    title: str
    position: int


@runtime_checkable
class BulkChapterReader(Protocol):
    """Load + validate chapters for a novel (raises ValidationError on bad ids)."""

    async def load(self, novel_id: UUID, chapter_ids: Sequence[UUID]) -> list[BulkChapterRef]: ...


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
        self, novel_id: UUID, owner_user_id: UUID, chapters: Sequence[BulkChapterRef]
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
    "BulkExtractionDispatcher",
    "BulkExtractionJobStore",
    "BulkExtractionPacer",
]
