"""BulkExtractionService unit tests (F2 T3, ADR-092 §4.6 + plan T5 list).

Covers: gate-before-load (IDOR ordering), reader-driven start validation
(422 pass-through), the single-active-job 409, position ordering, dispatch
on start AND on resume (spec §4.5 — a reset without re-dispatch would hang
a PENDING job), and the plain (job_id, user_id) delegation of
status/results/cancel.

The store/reader/dispatcher fakes implement the T1 Protocols (RULE-23 —
no mocks); the novel-gate fake backs ``verify_novel_owned``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.kb.bulk_extraction.contracts import (
    BulkChapterReader,
    BulkChapterRef,
    BulkExtractionDispatcher,
    BulkExtractionJobStore,
)
from narrare.kb.bulk_extraction.schemas import (
    BulkExtractionJobView,
    BulkExtractionResultsView,
    BulkExtractionStatusView,
    BulkExtractionTotals,
    BulkJobStatus,
)
from narrare.kb.bulk_extraction.service import BulkExtractionService
from narrare.novels.models import Novel
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

OWNER = uuid4()
NOVEL_ID = uuid4()
NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def _ref(position: int) -> BulkChapterRef:
    return BulkChapterRef(uuid4(), f"Chapter {position}", position)


def _job_view(
    status: BulkJobStatus = BulkJobStatus.PENDING,
    job_id: str = "job-1",
    novel_id: UUID = NOVEL_ID,
) -> BulkExtractionJobView:
    return BulkExtractionJobView(
        job_id=job_id,
        novel_id=novel_id,
        status=status,
        created_at=NOW,
        updated_at=NOW,
        totals=BulkExtractionTotals(total=2, done=0, failed=0, remaining=2),
        error=None,
    )


def _status_view(novel_id: UUID = NOVEL_ID) -> BulkExtractionStatusView:
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


def _results_view(novel_id: UUID = NOVEL_ID) -> BulkExtractionResultsView:
    return BulkExtractionResultsView(
        job_id="job-1", novel_id=novel_id, status=BulkJobStatus.COMPLETED, chapters=[]
    )


class _FakeStore:
    """BulkExtractionJobStore fake: records calls, returns canned views.

    ``active`` drives ``has_active_for``; ``cancel_error``/``resume_error``
    script the store-side ConflictError paths.
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
        # Novel every canned view is bound to (defaults to the harness novel).
        # Overridden by the novel-job-binding tests to simulate operating a
        # job of another novel under this novel's URL.
        self.bound_novel_id = bound_novel_id or NOVEL_ID
        self.created_with: tuple[UUID, UUID, list[BulkChapterRef]] | None = None
        self.read_calls: list[tuple[str, str, UUID]] = []

    async def create_job(
        self, novel_id: UUID, owner_user_id: UUID, chapters: Sequence[BulkChapterRef]
    ) -> BulkExtractionJobView:
        self.created_with = (novel_id, owner_user_id, list(chapters))
        return _job_view()

    async def get_status(self, job_id: str, user_id: UUID) -> BulkExtractionStatusView:
        self.read_calls.append(("get_status", job_id, user_id))
        return _status_view(novel_id=self.bound_novel_id)

    async def get_results(self, job_id: str, user_id: UUID) -> BulkExtractionResultsView:
        self.read_calls.append(("get_results", job_id, user_id))
        return _results_view(novel_id=self.bound_novel_id)

    async def cancel_job(self, job_id: str, user_id: UUID) -> BulkExtractionJobView:
        self.read_calls.append(("cancel_job", job_id, user_id))
        if self.cancel_error is not None:
            raise self.cancel_error
        return _job_view(BulkJobStatus.CANCELLING, novel_id=self.bound_novel_id)

    async def resume_job(self, job_id: str, user_id: UUID) -> BulkExtractionJobView:
        self.read_calls.append(("resume_job", job_id, user_id))
        if self.resume_error is not None:
            raise self.resume_error
        return _job_view(BulkJobStatus.PENDING, job_id=job_id, novel_id=self.bound_novel_id)

    async def has_active_for(self, novel_id: UUID) -> bool:
        return self.active


class _FakeReader:
    """BulkChapterReader fake: canned refs or a scripted ValidationError."""

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


class _FakeDispatcher:
    """BulkExtractionDispatcher fake: records every dispatch."""

    def __init__(self) -> None:
        self.dispatched: list[tuple[str, UUID, UUID]] = []

    async def dispatch(self, job_id: str, novel_id: UUID, owner_id: UUID) -> None:
        self.dispatched.append((job_id, novel_id, owner_id))


def _owned_novel_repo() -> FakeNovelRepository:
    """Gate repo with the owned novel seeded (gate passes)."""
    repo = FakeNovelRepository()
    repo.seed(Novel(id=NOVEL_ID, user_id=OWNER, title="Owned"))
    return repo


def _foreign_novel_repo() -> FakeNovelRepository:
    """Gate repo with NOTHING seeded — foreign ≡ unknown → the gate 404s."""
    return FakeNovelRepository()


class _Harness:
    """The service plus its four fakes, wired exactly as production would."""

    def __init__(
        self,
        *,
        store: _FakeStore | None = None,
        reader: _FakeReader | None = None,
        novel_repo: FakeNovelRepository | None = None,
    ) -> None:
        self.store = store or _FakeStore()
        self.reader = reader or _FakeReader()
        self.dispatcher = _FakeDispatcher()
        self.novel_repo = novel_repo or _owned_novel_repo()
        self.service = BulkExtractionService(
            store=self.store,
            reader=self.reader,
            dispatcher=self.dispatcher,
            novel_repo=self.novel_repo,
        )


class TestProtocolConformance:
    def test_fakes_satisfy_the_t1_protocols(self) -> None:
        harness = _Harness()
        assert isinstance(harness.store, BulkExtractionJobStore)
        assert isinstance(harness.reader, BulkChapterReader)
        assert isinstance(harness.dispatcher, BulkExtractionDispatcher)


class TestStart:
    async def test_gates_ownership_before_anything_else(self) -> None:
        harness = _Harness(novel_repo=_foreign_novel_repo())

        with pytest.raises(NotFoundError, match="Novel"):
            await harness.service.start(NOVEL_ID, OWNER, [uuid4()])

        assert len(harness.novel_repo.calls) == 1  # the gate ran (and only it)
        assert harness.reader.load_calls == []  # gate BEFORE load (IDOR ordering)
        assert harness.store.created_with is None
        assert harness.dispatcher.dispatched == []

    async def test_orders_refs_by_position_before_create(self) -> None:
        requested = [uuid4(), uuid4()]
        harness = _Harness(reader=_FakeReader(refs=[_ref(5), _ref(1)]))

        view = await harness.service.start(NOVEL_ID, OWNER, requested)

        assert view.job_id == "job-1"
        assert harness.reader.load_calls == [(NOVEL_ID, tuple(requested))]
        assert harness.store.created_with is not None
        created_novel, created_owner, created_refs = harness.store.created_with
        assert (created_novel, created_owner) == (NOVEL_ID, OWNER)
        assert [ref.position for ref in created_refs] == [1, 5]  # server-sorted
        assert harness.dispatcher.dispatched == [("job-1", NOVEL_ID, OWNER)]

    async def test_rejects_active_job_before_create(self) -> None:
        harness = _Harness(store=_FakeStore(active=True))

        with pytest.raises(ConflictError, match="already active"):
            await harness.service.start(NOVEL_ID, OWNER, [uuid4()])

        assert harness.store.created_with is None  # 409 wins before any job is created
        assert harness.dispatcher.dispatched == []

    async def test_propagates_reader_validation(self) -> None:
        bad_id = uuid4()
        reader = _FakeReader(error=ValidationError(f"Chapter {bad_id} not found in novel"))
        harness = _Harness(reader=reader)

        with pytest.raises(ValidationError, match=str(bad_id)):
            await harness.service.start(NOVEL_ID, OWNER, [bad_id])

        assert harness.store.created_with is None
        assert harness.dispatcher.dispatched == []


class TestDelegation:
    async def test_status_delegates_with_job_and_user(self) -> None:
        harness = _Harness()

        view = await harness.service.status(NOVEL_ID, "job-1", OWNER)

        assert len(harness.novel_repo.calls) == 1  # gate once, then delegate
        assert harness.store.read_calls == [("get_status", "job-1", OWNER)]
        assert view.status is BulkJobStatus.RUNNING

    async def test_results_and_cancel_delegate(self) -> None:
        harness = _Harness()

        results = await harness.service.results(NOVEL_ID, "job-1", OWNER)
        job = await harness.service.cancel(NOVEL_ID, "job-1", OWNER)

        assert isinstance(results, BulkExtractionResultsView)
        assert job.status is BulkJobStatus.CANCELLING
        # cancel pre-reads the binding (mutating op), results does not.
        assert harness.store.read_calls == [
            ("get_results", "job-1", OWNER),
            ("get_status", "job-1", OWNER),
            ("cancel_job", "job-1", OWNER),
        ]

    async def test_cancel_conflict_from_store_propagates(self) -> None:
        harness = _Harness(
            store=_FakeStore(
                cancel_error=ConflictError("Bulk extraction job 'job-1' is already terminal")
            )
        )

        with pytest.raises(ConflictError, match="already terminal"):
            await harness.service.cancel(NOVEL_ID, "job-1", OWNER)

    async def test_gate_blocks_every_op_before_store(self) -> None:
        harness = _Harness(novel_repo=_foreign_novel_repo())

        with pytest.raises(NotFoundError):
            await harness.service.status(NOVEL_ID, "job-1", OWNER)
        with pytest.raises(NotFoundError):
            await harness.service.results(NOVEL_ID, "job-1", OWNER)
        with pytest.raises(NotFoundError):
            await harness.service.cancel(NOVEL_ID, "job-1", OWNER)
        with pytest.raises(NotFoundError):
            await harness.service.resume(NOVEL_ID, "job-1", OWNER)

        assert harness.store.read_calls == []


class TestResume:
    async def test_resume_resets_then_redispatches_same_job(self) -> None:
        harness = _Harness()

        view = await harness.service.resume(NOVEL_ID, "job-9", OWNER)

        assert view.status is BulkJobStatus.PENDING
        # Pre-read binding guard, then the reset (mutating op).
        assert harness.store.read_calls == [
            ("get_status", "job-9", OWNER),
            ("resume_job", "job-9", OWNER),
        ]
        assert harness.dispatcher.dispatched == [("job-9", NOVEL_ID, OWNER)]  # spec §4.5

    async def test_resume_conflict_skips_dispatch(self) -> None:
        harness = _Harness(
            store=_FakeStore(
                resume_error=ConflictError(
                    "Bulk extraction job 'job-1' can only resume from cancelled or failed"
                )
            )
        )

        with pytest.raises(ConflictError):
            await harness.service.resume(NOVEL_ID, "job-1", OWNER)

        assert harness.dispatcher.dispatched == []


class TestNovelJobBinding:
    """A store hit bound to a DIFFERENT novel than the path is a 404 (rider).

    Owner pinning alone does not bind a job to the novel in the URL: the
    user owning novels A and B could otherwise operate B's job under A's
    URL (the gate passes — A is theirs; the store lookup passes — the job
    is theirs). The service must compare ``view.novel_id`` against the
    path novel after every store read, with the registry's foreign ≡
    unknown ``NotFoundError`` (anti-enumeration).

    The MUTATING paths (cancel/resume) pre-read the binding BEFORE the
    store write (fix round 1): a check only after the write would let a
    misrouted resume reset B's job to PENDING and then block the runner
    launch — a stranded PENDING job that ``find_active_for_novel`` counts
    active, locking the novel until restart.
    """

    OTHER_NOVEL = uuid4()

    def _mismatched_harness(self) -> _Harness:
        return _Harness(store=_FakeStore(bound_novel_id=self.OTHER_NOVEL))

    async def test_status_of_another_novels_job_is_not_found(self) -> None:
        harness = self._mismatched_harness()

        with pytest.raises(NotFoundError, match="job-1"):
            await harness.service.status(NOVEL_ID, "job-1", OWNER)

        assert harness.store.read_calls == [("get_status", "job-1", OWNER)]  # reads only

    async def test_results_of_another_novels_job_is_not_found(self) -> None:
        harness = self._mismatched_harness()

        with pytest.raises(NotFoundError, match="job-1"):
            await harness.service.results(NOVEL_ID, "job-1", OWNER)

        assert harness.store.read_calls == [("get_results", "job-1", OWNER)]  # reads only

    async def test_cancel_of_another_novels_job_is_rejected_before_the_flip(self) -> None:
        harness = self._mismatched_harness()

        with pytest.raises(NotFoundError, match="job-1"):
            await harness.service.cancel(NOVEL_ID, "job-1", OWNER)

        # Rejected BEFORE the mutating store call — no cancelling flip.
        assert harness.store.read_calls == [("get_status", "job-1", OWNER)]

    async def test_resume_of_another_novels_job_is_rejected_before_the_reset(self) -> None:
        harness = self._mismatched_harness()

        with pytest.raises(NotFoundError, match="job-1"):
            await harness.service.resume(NOVEL_ID, "job-1", OWNER)

        # Rejected BEFORE the mutating store call — no reset, no runner.
        assert harness.store.read_calls == [("get_status", "job-1", OWNER)]
        assert harness.dispatcher.dispatched == []
