"""Shared fakes + view factories for the bulk extraction service tests.

One helper module so ``test_bulk_extraction_service.py`` stays under the
RULE-04 hard limit once the F3 corpus service tests joined (mirrors
``tests/unit/api/kb/_assist_fakes.py`` and the ``bulk_extraction/_runner_fakes.py``
precedent: underscore-prefixed, import-only helpers — no tests here). Test
modules import these under their original private names (``FakeStore as
_FakeStore``), so call sites stay unchanged.

Every fake implements a T1 bulk-extraction Protocol (RULE-TEST-01 — no
mocks); ``FakeNovelRepository`` (the gate fake) stays in ``tests/fakes``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from narrare.kb.bulk_extraction.contracts import (
    BulkChapterRef,
    CorpusChapterRow,
)
from narrare.kb.bulk_extraction.schemas import (
    BulkExtractionJobView,
    BulkExtractionResultsView,
    BulkExtractionStatusView,
    BulkExtractionTotals,
    BulkJobStatus,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare.kb.bulk_extraction.contracts import BulkJobKind
    from narrare_core.shared.errors import ConflictError, ValidationError

OWNER = uuid4()
NOVEL_ID = uuid4()
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def make_ref(position: int) -> BulkChapterRef:
    """A minimal chapter ref at the given position."""
    return BulkChapterRef(uuid4(), f"Chapter {position}", position)


def make_job_view(
    status: BulkJobStatus = BulkJobStatus.PENDING,
    job_id: str = "job-1",
    novel_id: UUID = NOVEL_ID,
    total: int = 2,
    error: str | None = None,
) -> BulkExtractionJobView:
    """A minimal job view (the fake store's canned create response)."""
    return BulkExtractionJobView(
        job_id=job_id,
        novel_id=novel_id,
        status=status,
        created_at=NOW,
        updated_at=NOW,
        totals=BulkExtractionTotals(total=total, done=0, failed=0, remaining=total),
        error=error,
    )


def make_status_view(novel_id: UUID = NOVEL_ID) -> BulkExtractionStatusView:
    """A RUNNING status view with one done chapter (the delegation canned hit)."""
    return BulkExtractionStatusView(
        job_id="job-1",
        novel_id=novel_id,
        status=BulkJobStatus.RUNNING,
        created_at=NOW,
        updated_at=NOW,
        totals=BulkExtractionTotals(total=2, done=1, failed=0, remaining=1),
        error=None,
        chapters=[],
    )


def make_results_view(novel_id: UUID = NOVEL_ID) -> BulkExtractionResultsView:
    """A COMPLETED results view (the delegation canned hit)."""
    return BulkExtractionResultsView(
        job_id="job-1", novel_id=novel_id, status=BulkJobStatus.COMPLETED, chapters=[]
    )


class FakeStore:
    """``BulkExtractionJobStore`` fake: records calls, returns canned views.

    ``active`` drives ``has_active_for``; ``cancel_error``/``resume_error``
    script the store-side ConflictError paths; ``bound_novel_id`` overrides
    the novel every canned view is bound to (novel-job-binding tests). The
    create call is recorded split into ``created_with`` (novel, owner,
    refs) and ``created_kind`` (``"explicit"`` | ``"corpus"`` — F3).
    """

    def __init__(
        self,
        *,
        active: bool = False,
        cancel_error: ConflictError | None = None,
        resume_error: ConflictError | None = None,
        bound_novel_id: UUID | None = None,
    ) -> None:
        self.active = active
        self.cancel_error = cancel_error
        self.resume_error = resume_error
        self.bound_novel_id = bound_novel_id or NOVEL_ID
        self.created_with: tuple[UUID, UUID, list[BulkChapterRef]] | None = None
        self.created_kind: BulkJobKind = "explicit"
        self.read_calls: list[tuple[str, str, UUID]] = []

    async def create_job(
        self,
        novel_id: UUID,
        owner_user_id: UUID,
        chapters: Sequence[BulkChapterRef],
        kind: BulkJobKind = "explicit",
    ) -> BulkExtractionJobView:
        self.created_with = (novel_id, owner_user_id, list(chapters))
        self.created_kind = kind
        return make_job_view(novel_id=novel_id, total=len(chapters))

    async def get_status(self, job_id: str, user_id: UUID) -> BulkExtractionStatusView:
        self.read_calls.append(("get_status", job_id, user_id))
        return make_status_view(novel_id=self.bound_novel_id)

    async def get_results(self, job_id: str, user_id: UUID) -> BulkExtractionResultsView:
        self.read_calls.append(("get_results", job_id, user_id))
        return make_results_view(novel_id=self.bound_novel_id)

    async def cancel_job(self, job_id: str, user_id: UUID) -> BulkExtractionJobView:
        self.read_calls.append(("cancel_job", job_id, user_id))
        if self.cancel_error is not None:
            raise self.cancel_error
        return make_job_view(BulkJobStatus.CANCELLING, novel_id=self.bound_novel_id)

    async def resume_job(self, job_id: str, user_id: UUID) -> BulkExtractionJobView:
        self.read_calls.append(("resume_job", job_id, user_id))
        if self.resume_error is not None:
            raise self.resume_error
        return make_job_view(BulkJobStatus.PENDING, job_id=job_id, novel_id=self.bound_novel_id)

    async def has_active_for(self, novel_id: UUID) -> bool:
        return self.active


class FakeReader:
    """``BulkChapterReader`` fake: canned refs or a scripted ValidationError."""

    def __init__(
        self,
        refs: list[BulkChapterRef] | None = None,
        error: ValidationError | None = None,
    ) -> None:
        self.refs = refs or []
        self.error = error
        self.load_calls: list[tuple[UUID, tuple[UUID, ...]]] = []

    async def load(self, novel_id: UUID, chapter_ids: Sequence[UUID]) -> list[BulkChapterRef]:
        self.load_calls.append((novel_id, tuple(chapter_ids)))
        if self.error is not None:
            raise self.error
        return self.refs


class FakeCorpusSource:
    """``CorpusChapterSource`` fake: replays scripted row lists per call.

    The LAST scripted list is sticky — an unscripted extra call (or a
    single-entry script polled twice) returns the same rows instead of a
    surprising empty novel.
    """

    def __init__(self, script: list[list[CorpusChapterRow]] | None = None) -> None:
        self._script = list(script or [])
        self.calls: list[UUID] = []

    async def load_all(self, novel_id: UUID) -> list[CorpusChapterRow]:
        self.calls.append(novel_id)
        if len(self._script) > 1:
            return self._script.pop(0)
        return self._script[0] if self._script else []


class FakeDispatcher:
    """``BulkExtractionDispatcher`` fake: records every dispatch."""

    def __init__(self) -> None:
        self.dispatched: list[tuple[str, UUID, UUID]] = []

    async def dispatch(self, job_id: str, novel_id: UUID, owner_id: UUID) -> None:
        self.dispatched.append((job_id, novel_id, owner_id))
