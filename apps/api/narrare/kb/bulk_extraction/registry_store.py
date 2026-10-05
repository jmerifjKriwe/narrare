"""Bulk-extraction registry store: runner-side mutations + maintenance.

The mutation half of the in-memory bulk extraction registry (ADR-092 §6).
The user-facing, owner-checked operations live in :mod:`narrare.kb.bulk_extraction.registry`;
the pure STATE (records, :data:`JOBS`, lifecycle partitions, clock) lives in
:mod:`narrare.kb.bulk_extraction.registry_records` — split off in F3 T2
(RULE-04: this module crossed its 400-line hard limit when the post-pass
dedup mutations landed). This module re-exports every state name, so the
one-import-seam rule holds: T4/T5/T6 keep coding against ``registry.*`` only.

Runner-time ``mark_*`` mutations are job-id-keyed: they only run for jobs the
service gate already admitted, and an unknown/swept id degrades to a logged
no-op (a background callback must never crash on swept state — RULE-11: the
warning is the queryable trace).

Concurrency: every mutation is synchronous (no ``await`` between read and
write), safe under the single-threaded asyncio loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb.bulk_extraction.contracts import BULK_JOB_TTL, BulkJobKind
from narrare.kb.bulk_extraction.registry_records import (
    ACTIVE,
    JOBS,
    RESUMABLE,
    TERMINAL,
    BulkChapterState,
    BulkJobRecord,
    BulkJobStatus,
    ChapterRecord,
    touch_record,
    utc_now,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from uuid import UUID

    from narrare_core.agents.extraction_types import ExtractionOutput

logger = structlog.get_logger(__name__)

__all__ = [
    "ACTIVE",
    "JOBS",
    "RESUMABLE",
    "TERMINAL",
    "BulkChapterState",
    "BulkJobRecord",
    "BulkJobStatus",
    "ChapterRecord",
    "cancel_requested",
    "find_active_for_novel",
    "kind_of",
    "mark_cancelled",
    "mark_chapter_done",
    "mark_chapter_failed",
    "mark_chapter_running",
    "mark_dedup",
    "mark_dedup_unavailable",
    "mark_job_completed",
    "mark_job_failed",
    "mark_job_running",
    "pending_chapter_ids",
    "sweep_expired",
    "touch_record",
    "utc_now",
]


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

    Terminal-state guard: a job that already reached a terminal status is left
    untouched — a shutdown drain arriving after ``mark_job_completed`` (the
    post-pass dedup window makes this reachable) or after a user cancel/failed
    run must not overwrite the real outcome. The no-op is logged (RULE-11).
    """
    record = _get_unchecked(job_id, "mark_cancelled")
    if record is None:
        return
    if record.status in TERMINAL:
        logger.info(
            "bulk_cancel_skipped_terminal",
            job_id=job_id,
            status=record.status.value,
            requested_reason=reason,
        )
        return
    record.status = BulkJobStatus.CANCELLED
    record.error = reason
    record.expires_hint = utc_now() + BULK_JOB_TTL
    touch_record(record)
    logger.warning("bulk_job_cancelled", job_id=job_id, reason=reason)


def mark_dedup(job_id: str, suggestion_count: int) -> None:
    """Record a finished post-pass dedup analysis (corpus jobs; no-op if swept).

    Sets ``analyzed: true`` + the count in one flip — the wire invariant is
    ``suggestion_count`` present ⟺ ``analyzed`` (:class:`BulkDedupInfo`).
    """
    record = _get_unchecked(job_id, "mark_dedup")
    if record is None:
        return
    record.dedup_analyzed = True
    record.dedup_suggestion_count = suggestion_count
    touch_record(record)
    logger.info("bulk_dedup_analyzed", job_id=job_id, suggestion_count=suggestion_count)


def mark_dedup_unavailable(job_id: str) -> None:
    """Record a FAILED post-pass analysis — visible, non-fatal (RULE-11).

    Resets the block to its default (``analyzed: false``); the job itself
    stays completed — the pass succeeded, only the duplicate check is out.
    """
    record = _get_unchecked(job_id, "mark_dedup_unavailable")
    if record is None:
        return
    record.dedup_analyzed = False
    record.dedup_suggestion_count = None
    touch_record(record)
    logger.warning("bulk_dedup_unavailable", job_id=job_id)


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


def kind_of(job_id: str) -> BulkJobKind:
    """The job's kind — ``"corpus"`` arms the post-pass dedup trigger (F3 §6).

    Runner-side lookup: an unknown/swept id degrades to ``"explicit"`` (the
    no-trigger kind) with a logged trace — a background callback must never
    arm a trigger on state it cannot see.
    """
    record = JOBS.get(job_id)
    if record is None:
        logger.warning("bulk_unknown_job", job_id=job_id, action="kind_of")
        return "explicit"
    return record.kind


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
