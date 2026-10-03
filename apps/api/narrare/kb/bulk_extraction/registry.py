"""In-memory bulk-extraction job registry — user-facing operations (ADR-092 §6).

Public seam of the bulk extraction job registry: the owner-checked request-path
operations (create/status/results/cancel/resume) plus re-exports of the
runner-side mutations from :mod:`narrare.kb.bulk_extraction.registry_store`
(state, ``mark_*``, sweep). T4/T5/T6 code against ``registry.*`` only — the
names are pinned by the approved plan.

Mirrors ``narrare.export.registry`` (third module-local registry — no shared
abstraction yet). The store is **process-local by design** and is NOT drained
on shutdown; see ``registry_store`` for the state/GC-guard story. The module
split follows RULE-04 (the combined file exceeded the 400-line hard limit).

Owner pinning (foreign ≡ unknown)
---------------------------------
Every record carries ``owner_user_id``, bound at :func:`create` — i.e. after
the service's owned-novel gate, so the binding is trustworthy by
construction. The ops below take the caller's ``user_id`` and treat an owner
mismatch exactly like an unknown job id — same
:class:`~narrare_core.shared.errors.NotFoundError`, same message
(anti-enumeration; mirrors ``export/registry.py:145-155``). Runner-time
``mark_*`` mutations stay job-id-keyed (see ``registry_store``).

Views are always derived: totals are recomputed from the per-chapter rows on
every read, so a status poll can never show stale aggregates. Concurrent
safety comes from synchronous mutations under the single asyncio loop.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import structlog

from narrare.kb.bulk_extraction.registry_store import (
    JOBS as _JOBS,
)
from narrare.kb.bulk_extraction.registry_store import (
    BulkJobRecord as _BulkJobRecord,
)
from narrare.kb.bulk_extraction.registry_store import (
    ChapterRecord as _ChapterRecord,
)
from narrare.kb.bulk_extraction.registry_store import (
    cancel_requested,
    find_active_for_novel,
    mark_cancelled,
    mark_chapter_done,
    mark_chapter_failed,
    mark_chapter_running,
    mark_job_completed,
    mark_job_failed,
    mark_job_running,
    pending_chapter_ids,
    sweep_expired,
)
from narrare.kb.bulk_extraction.registry_store import (
    touch_record as _touch,
)
from narrare.kb.bulk_extraction.registry_store import (
    utc_now as _now,
)
from narrare.kb.bulk_extraction.schemas import (
    BulkChapterState,
    BulkChapterStatusView,
    BulkExtractionJobView,
    BulkExtractionResultChapter,
    BulkExtractionResultsView,
    BulkExtractionStatusView,
    BulkExtractionTotals,
    BulkJobStatus,
)
from narrare_core.shared.errors import ConflictError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.kb.bulk_extraction.contracts import BulkChapterRef

logger = structlog.get_logger(__name__)

#: Job statuses that end the lifecycle — cancel/resume conflict on them.
_TERMINAL: frozenset[BulkJobStatus] = frozenset(
    {
        BulkJobStatus.COMPLETED,
        BulkJobStatus.CANCELLED,
        BulkJobStatus.FAILED,
    }
)

#: Job statuses a resume may start from (spec §4.5).
_RESUMABLE: frozenset[BulkJobStatus] = frozenset(
    {
        BulkJobStatus.CANCELLED,
        BulkJobStatus.FAILED,
    }
)


def _get_owned(job_id: str, user_id: UUID) -> _BulkJobRecord:
    """Return the record for an owner-approved job id (foreign ≡ unknown).

    Raises :class:`NotFoundError` with the *same* message for unknown ids and
    jobs owned by another user — no enumeration oracle. The shared error's
    constructor appends ``" not found"`` to its ``resource`` argument, so the
    resource carries the job phrase and ``str(exc)`` comes out as
    ``"Bulk extraction job '<id>' not found"`` (export registry shape).
    """
    record = _JOBS.get(job_id)
    if record is None or record.owner_user_id != user_id:
        raise NotFoundError(f"Bulk extraction job '{job_id}'")
    return record


def _totals(record: _BulkJobRecord) -> BulkExtractionTotals:
    """Recompute the aggregate counts (views are always derived, §6)."""
    done = sum(1 for c in record.chapters if c.state is BulkChapterState.DONE)
    failed = sum(1 for c in record.chapters if c.state is BulkChapterState.FAILED)
    total = len(record.chapters)
    return BulkExtractionTotals(
        total=total, done=done, failed=failed, remaining=total - done - failed
    )


def _job_view(record: _BulkJobRecord) -> BulkExtractionJobView:
    return BulkExtractionJobView(
        job_id=record.job_id,
        novel_id=record.novel_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        totals=_totals(record),
        error=record.error,
    )


# ── User-facing operations (owner-checked) ─────────────────────────────────


def create(
    novel_id: UUID, owner_user_id: UUID, chapters: Sequence[BulkChapterRef]
) -> BulkExtractionJobView:
    """Register a PENDING job owned by ``owner_user_id`` and return its view.

    The service calls this only AFTER the owned-novel gate passed, so the
    owner binding is trustworthy by construction. The job id is an opaque
    ``secrets.token_urlsafe(16)`` token. Chapters are stored in position
    order (the job's canonical order — spec §4.1), regardless of request
    order.
    """
    record = _BulkJobRecord(
        job_id=secrets.token_urlsafe(16),
        novel_id=novel_id,
        owner_user_id=owner_user_id,
        created_at=_now(),
        updated_at=_now(),
        chapters=[
            _ChapterRecord(chapter_id=c.chapter_id, title=c.title, position=c.position)
            for c in sorted(chapters, key=lambda ref: ref.position)
        ],
    )
    _JOBS[record.job_id] = record
    logger.info(
        "bulk_job_created",
        job_id=record.job_id,
        novel_id=str(novel_id),
        chapter_count=len(record.chapters),
    )
    return _job_view(record)


def status(job_id: str, user_id: UUID) -> BulkExtractionStatusView:
    """Poll one job: the derived job view plus per-chapter rows (owner-only)."""
    record = _get_owned(job_id, user_id)
    chapters = [
        BulkChapterStatusView(
            chapter_id=c.chapter_id,
            title=c.title,
            position=c.position,
            state=c.state,
            item_count=c.item_count,
            error=c.error,
        )
        for c in record.chapters
    ]
    return BulkExtractionStatusView(
        job_id=record.job_id,
        novel_id=record.novel_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        totals=_totals(record),
        error=record.error,
        chapters=chapters,
    )


def results(job_id: str, user_id: UUID) -> BulkExtractionResultsView:
    """Full outputs for the review panel (owner-only, any job state).

    Includes every chapter in position order; ``output`` is present only on
    ``done`` rows (partial results of a cancelled job stay readable — the
    resume baseline, spec §4.3).
    """
    record = _get_owned(job_id, user_id)
    chapters = [
        BulkExtractionResultChapter(
            chapter_id=c.chapter_id,
            title=c.title,
            position=c.position,
            state=c.state,
            output=c.output if c.state is BulkChapterState.DONE else None,
        )
        for c in record.chapters
    ]
    return BulkExtractionResultsView(
        job_id=record.job_id, novel_id=record.novel_id, status=record.status, chapters=chapters
    )


def request_cancel(job_id: str, user_id: UUID) -> BulkExtractionJobView:
    """Set the cooperative cancel flag; status → ``cancelling`` (owner-only).

    The runner honours the flag between chapters — the in-flight chapter
    completes and is recorded first (spec §4.4). A terminal job cannot be
    cancelled: :class:`ConflictError` (409).
    """
    record = _get_owned(job_id, user_id)
    if record.status in _TERMINAL:
        raise ConflictError(
            f"Bulk extraction job '{job_id}' is already terminal (status: {record.status.value})"
        )
    record.cancel_requested = True
    record.status = BulkJobStatus.CANCELLING
    _touch(record)
    logger.info("bulk_job_cancel_requested", job_id=job_id)
    return _job_view(record)


def reset_for_resume(job_id: str, user_id: UUID) -> BulkExtractionJobView:
    """Reset a cancelled/failed job so a fresh runner can re-dispatch it.

    Only ``cancelled | failed`` qualify (:class:`ConflictError` otherwise).
    Every non-``done`` chapter (pending, stranded-by-drain running, failed)
    goes back to ``pending`` with its stale ``error`` cleared — a re-pended
    row must not carry a failure reason from the previous attempt, and the
    runner's ``pending_chapter_ids`` worklist would silently lose a chapter
    left in a stale state. ``done`` chapters keep their output and
    ``item_count`` (the reviewable baseline, spec §4.5). The cancel flag and
    job-level error are cleared (a resumed job must not re-cancel itself or
    resurrect the old failure), and the sweep hint is withdrawn (the job is
    non-terminal again).
    """
    record = _get_owned(job_id, user_id)
    if record.status not in _RESUMABLE:
        raise ConflictError(
            f"Bulk extraction job '{job_id}' can only resume from cancelled or failed "
            f"(status: {record.status.value})"
        )
    for chapter in record.chapters:
        if chapter.state is not BulkChapterState.DONE:
            chapter.state = BulkChapterState.PENDING
            chapter.error = None
    record.status = BulkJobStatus.PENDING
    record.error = None
    record.cancel_requested = False
    record.expires_hint = None
    _touch(record)
    logger.info("bulk_job_resumed", job_id=job_id)
    return _job_view(record)


# Runner-side names, re-exported so callers have ONE import seam (pinned by
# the plan: T4 monkeypatches ``runner.registry`` and calls these on it).
__all__ = [
    "_JOBS",
    "cancel_requested",
    "create",
    "find_active_for_novel",
    "mark_cancelled",
    "mark_chapter_done",
    "mark_chapter_failed",
    "mark_chapter_running",
    "mark_job_completed",
    "mark_job_failed",
    "mark_job_running",
    "pending_chapter_ids",
    "request_cancel",
    "reset_for_resume",
    "results",
    "status",
    "sweep_expired",
]
