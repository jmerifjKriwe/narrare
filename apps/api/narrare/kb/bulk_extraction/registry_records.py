"""Bulk-extraction registry STATE — records, shared dicts, lifecycle sets.

The data half of the in-memory bulk extraction registry (ADR-092 §6), split
from :mod:`narrare.kb.bulk_extraction.registry_store` in F3 T2 (RULE-04:
that module crossed its 400-line hard limit when the post-pass dedup state
landed — the split follows the module's own documented axis, "data, not a
task", vs the runner-side mutations that consume the data). ``registry_store``
re-exports every name here, so the one-import-seam rule holds: T4/T5/T6 code
against ``registry.*`` only.

Process-local by design — the :data:`JOBS` dict lives in memory for the API
process's lifetime and is lost on restart; a polled job id then surfaces as
:class:`~narrare_core.shared.errors.NotFoundError` and the FE degrades to its
"interrupted" state (spec §9). Nothing of value is lost: extraction results
are re-runnable proposals until explicitly endorsed (ADR-092 decision 2).

This module is **data, not a task** — it is NOT drained on shutdown. The
in-flight runner coroutines live in ``narrare.kb.bulk_extraction.runner``
(``_INFLIGHT_TASKS`` with a done-callback GC guard, mirroring
``export/tasks.py:188-212``); the drain cancels those tasks and their
done-callback flips the job to CANCELLED via ``mark_cancelled``. The
registry is just the state those coroutines mutate.

Concurrency: every mutation is synchronous (no ``await`` between read and
write), safe under the single-threaded asyncio loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from narrare.kb.bulk_extraction.contracts import (
    BulkChapterState,
    BulkJobKind,
    BulkJobStatus,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.agents.extraction_types import ExtractionOutput


#: Job statuses that block a new job for the same novel (spec §4.1: 409).
ACTIVE: Final[frozenset[BulkJobStatus]] = frozenset(
    {
        BulkJobStatus.PENDING,
        BulkJobStatus.RUNNING,
        BulkJobStatus.CANCELLING,
    }
)

#: Job statuses that end the lifecycle — cancel/resume conflict on them.
#: Single definition point for the terminal partition; ``registry`` imports
#: it under its private ``_TERMINAL`` name (usage sites unchanged).
TERMINAL: Final[frozenset[BulkJobStatus]] = frozenset(
    {
        BulkJobStatus.COMPLETED,
        BulkJobStatus.CANCELLED,
        BulkJobStatus.FAILED,
    }
)

#: Job statuses a resume may start from (spec §4.5). Single definition point
#: for the resumable partition; ``registry`` imports it under its private
#: ``_RESUMABLE`` name (usage sites unchanged).
RESUMABLE: Final[frozenset[BulkJobStatus]] = frozenset(
    {
        BulkJobStatus.CANCELLED,
        BulkJobStatus.FAILED,
    }
)


def utc_now() -> datetime:
    """Timezone-aware "now" (mirrors the tz-aware DB columns)."""
    return datetime.now(UTC)


@dataclass
class ChapterRecord:
    """Mutable per-chapter state (position-sorted, one row per job chapter).

    ``output`` is the full :class:`ExtractionOutput`, stored only by
    ``mark_chapter_done`` — so ``output is not None ⟺ state = done`` holds
    by construction and the wire validators can never trip.
    """

    chapter_id: UUID
    title: str
    position: int
    state: BulkChapterState = BulkChapterState.PENDING
    item_count: int | None = None
    error: str | None = None  # expected on failed rows; cleared on reset
    output: ExtractionOutput | None = None


@dataclass
class BulkJobRecord:
    """Mutable in-memory state for one bulk extraction job.

    ``owner_user_id`` is pinned at create time (after the owned-novel gate —
    see :mod:`narrare.kb.bulk_extraction.registry`); user-facing ops treat any
    other user as if the job did not exist. ``expires_hint`` is set only when
    the job reaches a terminal status (``utc_now() + BULK_JOB_TTL``) — it is the
    sole basis of ``sweep_expired``, so non-terminal jobs are never swept.

    ``kind`` (F3) discriminates ``explicit`` engine jobs from ``corpus`` pass
    jobs; only corpus jobs arm the post-pass dedup trigger, whose outcome is
    the (``dedup_analyzed``, ``dedup_suggestion_count``) pair — flipped by
    ``mark_dedup`` / ``mark_dedup_unavailable`` and surfaced on the
    status/results views (``None`` for explicit jobs).
    """

    job_id: str
    novel_id: UUID
    owner_user_id: UUID
    created_at: datetime
    updated_at: datetime
    chapters: list[ChapterRecord]
    status: BulkJobStatus = BulkJobStatus.PENDING
    error: str | None = None  # expected on failed rows; cancelled jobs carry the terminal reason
    cancel_requested: bool = False
    expires_hint: datetime | None = None
    kind: BulkJobKind = "explicit"
    dedup_analyzed: bool = False
    dedup_suggestion_count: int | None = None


#: ``job_id`` → record. Process-local (ADR-092). Accessed from the request
#: path (user-facing ops in ``registry.py``) and the background runner
#: (``mark_*``). Safe under the single-threaded asyncio loop: every mutation
#: is synchronous.
JOBS: dict[str, BulkJobRecord] = {}


def touch_record(record: BulkJobRecord) -> None:
    record.updated_at = utc_now()
