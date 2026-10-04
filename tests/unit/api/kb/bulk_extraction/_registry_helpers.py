"""Shared factories + clock kit for the bulk extraction registry tests.

One helper module so ``test_registry.py`` stays under the RULE-04 hard
limit; mirrors the ``tests/unit/api/kb/bulk_extraction/_runner_fakes.py``
precedent (underscore-prefixed, import-only helpers — no tests here).
``test_registry.py`` and ``test_registry_sweep.py`` import these under
their original private names (``make_job as _make_job``), so call sites
are unchanged.

Fresh UUIDs per import are safe: registry state is process-global and
every test module clears it via its autouse ``_clear_jobs`` fixture.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.kb.bulk_extraction import registry
from narrare.kb.bulk_extraction.contracts import BulkChapterRef
from narrare.kb.bulk_extraction.schemas import BulkJobStatus

if TYPE_CHECKING:
    from uuid import UUID

OWNER = uuid4()
FOREIGN = uuid4()
NOVEL_ID = uuid4()

#: The terminal statuses (sweepable, cancel/resume conflict).
TERMINAL = [BulkJobStatus.COMPLETED, BulkJobStatus.CANCELLED, BulkJobStatus.FAILED]

FROZEN_NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def make_ref(position: int) -> BulkChapterRef:
    """A minimal chapter ref at the given position."""
    return BulkChapterRef(uuid4(), "T", position)


def make_job(*positions: int, owner: UUID = OWNER, novel_id: UUID = NOVEL_ID) -> str:
    """Create a job with one chapter per given position (owner-checked path)."""
    return registry.create(novel_id, owner, [make_ref(p) for p in positions]).job_id


def drive_to(job_id: str, status: BulkJobStatus) -> None:
    """Drive a fresh single-chapter job into the given job status."""
    if status is BulkJobStatus.PENDING:
        return
    registry.mark_job_running(job_id)
    if status is BulkJobStatus.RUNNING:
        return
    if status is BulkJobStatus.CANCELLING:
        registry.request_cancel(job_id, OWNER)
        return
    if status is BulkJobStatus.COMPLETED:
        registry.mark_job_completed(job_id)
        return
    if status is BulkJobStatus.FAILED:
        registry.mark_job_failed(job_id, "boom")
        return
    registry.request_cancel(job_id, OWNER)
    registry.mark_cancelled(job_id, "cancelled by user")
