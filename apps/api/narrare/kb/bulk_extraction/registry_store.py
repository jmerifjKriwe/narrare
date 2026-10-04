"""Bulk-extraction registry store: shared state + runner-side mutations.

The state half of the in-memory bulk extraction registry (ADR-092 §6). The
user-facing, owner-checked operations live in :mod:`narrare.kb.bulk_extraction.registry`,
which re-exports the runner-facing names defined here — T4/T5 keep coding
against ``registry.*`` only. Split reason: RULE-04 (the combined module
exceeded the 400-line hard limit), along the module's real axis: request-path
ops vs background-runner mutations.

Process-local by design — the ``JOBS`` dict lives in memory for the API
process's lifetime and is lost on restart; a polled job id then surfaces as
:class:`~narrare_core.shared.errors.NotFoundError` and the FE degrades to its
"interrupted" state (spec §9). Nothing of value is lost: extraction results
are re-runnable proposals until explicitly endorsed (ADR-092 decision 2).

This module is **data, not a task** — it is NOT drained on shutdown. The
in-flight runner coroutines live in ``narrare.kb.bulk_extraction.runner``
(``_INFLIGHT_TASKS`` with a done-callback GC guard, mirroring
``export/tasks.py:188-212``); the drain cancels those tasks and their
done-callback flips the job to CANCELLED via :func:`mark_cancelled`
(``"cancelled (server shutdown)"``). The registry is just the state those
coroutines mutate.

Runner-time ``mark_*`` mutations are job-id-keyed: they only run for jobs the
service gate already admitted, and an unknown/swept id degrades to a logged
no-op (a background callback must never crash on swept state — RULE-11: the
warning is the queryable trace).

Concurrency: every mutation is synchronous (no ``await`` between read and
write), safe under the single-threaded asyncio loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

import structlog

from narrare.kb.bulk_extraction.contracts import BULK_JOB_TTL
from narrare.kb.bulk_extraction.schemas import BulkChapterState, BulkJobStatus

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from narrare_core.agents.extraction_types import ExtractionOutput

logger = structlog.get_logger(__name__)

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
    :func:`mark_chapter_done` — so ``output is not None ⟺ state = done``
    holds by construction and the wire validators can never trip.
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
    sole basis of :func:`sweep_expired`, so non-terminal jobs are never swept.
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


#: ``job_id`` → record. Process-local (ADR-092). Accessed from the request
#: path (user-facing ops in ``registry.py``) and the background runner
#: (``mark_*``). Safe under the single-threaded asyncio loop: every mutation
#: is synchronous.
JOBS: dict[str, BulkJobRecord] = {}


def touch_record(record: BulkJobRecord) -> None:
    record.updated_at = utc_now()


def _get_unchecked(job_id: str, action: str) -> BulkJobRecord | None:
    """Runner-side lookup: ``None`` (logged) for unknown/swept job ids."""
    record = JOBS.get(job_id)
    if record is None:
        logger.warning("bulk_mark_unknown_job", job_id=job_id, action=action)
    return record


def _find_chapter(record: BulkJobRecord, chapter_id: UUID) -> ChapterRecord | None:
    return next((c for c in record.chapters if c.chapter_id == chapter_id), None)


# ── Runner-time mutations (job-id-keyed; unknown id → logged no-op) ────────


def mark_job_running(job_id: str) -> None:
    """Flip a PENDING job to RUNNING (no-op if the job was swept)."""
    record = _get_unchecked(job_id, "mark_job_running")
    if record is None:
        return
    record.status = BulkJobStatus.RUNNING
    touch_record(record)


def mark_chapter_running(job_id: str, chapter_id: UUID) -> None:
    """Flip one chapter to RUNNING (no-op on unknown job or chapter)."""
    record = _get_unchecked(job_id, "mark_chapter_running")
    if record is None:
        return
    chapter = _find_chapter(record, chapter_id)
    if chapter is None:
        logger.warning(
            "bulk_mark_unknown_chapter",
            job_id=job_id,
            chapter_id=str(chapter_id),
            action="mark_chapter_running",
        )
        return
    chapter.state = BulkChapterState.RUNNING
    touch_record(record)


def mark_chapter_done(job_id: str, chapter_id: UUID, output: ExtractionOutput) -> None:
    """Record one chapter's full output; ``item_count = len(output.results)``."""
    record = _get_unchecked(job_id, "mark_chapter_done")
    if record is None:
        return
    chapter = _find_chapter(record, chapter_id)
    if chapter is None:
        logger.warning(
            "bulk_mark_unknown_chapter",
            job_id=job_id,
            chapter_id=str(chapter_id),
            action="mark_chapter_done",
        )
        return
    chapter.state = BulkChapterState.DONE
    chapter.output = output
    chapter.item_count = len(output.results)
    chapter.error = None
    touch_record(record)
    logger.debug(
        "bulk_chapter_done",
        job_id=job_id,
        chapter_id=str(chapter_id),
        item_count=chapter.item_count,
    )


def mark_chapter_failed(job_id: str, chapter_id: UUID, error: str) -> None:
    """Record one chapter's failure; the job continues (spec §5 isolation)."""
    record = _get_unchecked(job_id, "mark_chapter_failed")
    if record is None:
        return
    chapter = _find_chapter(record, chapter_id)
    if chapter is None:
        logger.warning(
            "bulk_mark_unknown_chapter",
            job_id=job_id,
            chapter_id=str(chapter_id),
            action="mark_chapter_failed",
        )
        return
    chapter.state = BulkChapterState.FAILED
    chapter.error = error
    touch_record(record)
    logger.warning("bulk_chapter_failed", job_id=job_id, chapter_id=str(chapter_id), error=error)


def mark_job_completed(job_id: str) -> None:
    """Flip a finished job to COMPLETED and arm the TTL sweep hint."""
    record = _get_unchecked(job_id, "mark_job_completed")
    if record is None:
        return
    record.status = BulkJobStatus.COMPLETED
    record.expires_hint = utc_now() + BULK_JOB_TTL
    touch_record(record)
    logger.info("bulk_job_completed", job_id=job_id)


def mark_job_failed(job_id: str, error: str) -> None:
    """Flip a job to FAILED with a typed reason (e.g. ``ConfigurationError``)."""
    record = _get_unchecked(job_id, "mark_job_failed")
    if record is None:
        return
    record.status = BulkJobStatus.FAILED
    record.error = error
    record.expires_hint = utc_now() + BULK_JOB_TTL
    touch_record(record)
    logger.warning("bulk_job_failed", job_id=job_id, error=error)


def mark_cancelled(job_id: str, reason: str) -> None:
    """Flip a job to CANCELLED; ``reason`` is client-visible (spec §9 banner).

    Used by the runner's cooperative-cancel stop and by the drain done-callback
    (``"cancelled (server shutdown)"``, mirroring ``export/tasks.py:188-212``).
    """
    record = _get_unchecked(job_id, "mark_cancelled")
    if record is None:
        return
    record.status = BulkJobStatus.CANCELLED
    record.error = reason
    record.expires_hint = utc_now() + BULK_JOB_TTL
    touch_record(record)
    logger.warning("bulk_job_cancelled", job_id=job_id, reason=reason)


# ── Runner helpers / maintenance (job-id- or novel-keyed) ──────────────────


def cancel_requested(job_id: str) -> bool:
    """Whether the user asked to cancel (checked between chapters)."""
    record = JOBS.get(job_id)
    if record is None:
        logger.warning("bulk_unknown_job", job_id=job_id, action="cancel_requested")
        return False
    return record.cancel_requested


def pending_chapter_ids(job_id: str) -> list[UUID]:
    """Snapshot of pending chapter ids in position order.

    A terminal job can carry a stranded-RUNNING row only via a mid-chapter
    drain; :func:`narrare.kb.bulk_extraction.registry.reset_for_resume`
    re-pends those before a runner can re-dispatch, so filtering on
    ``pending`` here is lossless. The returned list is a fresh snapshot —
    callers may mutate it freely.
    """
    record = JOBS.get(job_id)
    if record is None:
        logger.warning("bulk_unknown_job", job_id=job_id, action="pending_chapter_ids")
        return []
    return [c.chapter_id for c in record.chapters if c.state is BulkChapterState.PENDING]


def find_active_for_novel(novel_id: UUID) -> str | None:
    """The id of the novel's active job (``pending|running|cancelling``), if any.

    ``service.start`` turns a hit into a 409 (single active job per novel,
    spec §4.1/§6). Scan order is insertion order; the service gate makes
    multiples unreachable.
    """
    for job_id, record in JOBS.items():
        if record.novel_id == novel_id and record.status in ACTIVE:
            return job_id
    return None


def sweep_expired(now: Callable[[], datetime] = utc_now) -> int:
    """Drop terminal jobs whose ``BULK_JOB_TTL`` (24 h) elapsed; return count.

    Only records with an ``expires_hint`` (set when a job went terminal) can
    be dropped — a running/pending job is never swept. Idempotent; hooked into
    the lifespan periodic-cleanup loop next to the export registry's sweep.
    """
    dropped = 0
    for job_id in list(JOBS):
        record = JOBS[job_id]
        if record.expires_hint is None or now() <= record.expires_hint:
            continue
        del JOBS[job_id]
        dropped += 1
        logger.info("bulk_job_swept", job_id=job_id)
    return dropped


__all__ = [
    "JOBS",
    "BulkJobRecord",
    "cancel_requested",
    "find_active_for_novel",
    "mark_cancelled",
    "mark_chapter_done",
    "mark_chapter_failed",
    "mark_chapter_running",
    "mark_job_completed",
    "mark_job_failed",
    "mark_job_running",
    "pending_chapter_ids",
    "sweep_expired",
]
