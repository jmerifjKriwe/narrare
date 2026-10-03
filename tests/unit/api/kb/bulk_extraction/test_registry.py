"""Registry semantics for the in-memory bulk extraction job store (F2 T2, ADR-092 §6).

Covers: owner pinning (foreign ≡ unknown → 404), the pending→running→done
lifecycle with derived totals, cooperative cancel + drain cancellation,
resume reset (done retained, failure reasons cleared), per-chapter failure
isolation, TTL sweep of terminal jobs, and the single-active-job scan.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.kb.bulk_extraction import registry, registry_store
from narrare.kb.bulk_extraction.contracts import BULK_JOB_TTL, BulkChapterRef
from narrare.kb.bulk_extraction.schemas import BulkChapterState, BulkJobStatus
from narrare_core.agents.extraction_types import ExtractionItem, ExtractionOutput
from narrare_core.shared.errors import ConflictError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

OWNER = uuid4()
FOREIGN = uuid4()
NOVEL_ID = uuid4()

#: The terminal statuses (sweepable, cancel/resume conflict).
_TERMINAL = [BulkJobStatus.COMPLETED, BulkJobStatus.CANCELLED, BulkJobStatus.FAILED]

#: Statuses resume is forbidden from (spec §4.5).
_NOT_RESUMABLE = [
    BulkJobStatus.PENDING,
    BulkJobStatus.RUNNING,
    BulkJobStatus.CANCELLING,
    BulkJobStatus.COMPLETED,
]

_FROZEN_NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def _ref(position: int) -> BulkChapterRef:
    return BulkChapterRef(uuid4(), "T", position)


def _output(n_items: int) -> ExtractionOutput:
    return ExtractionOutput(
        results=[
            ExtractionItem(
                item_type="new_entity", name=f"item-{i}", confidence=0.9, source_text="s"
            )
            for i in range(n_items)
        ],
    )


def _make_job(*positions: int, owner: UUID = OWNER, novel_id: UUID = NOVEL_ID) -> str:
    return registry.create(novel_id, owner, [_ref(p) for p in positions]).job_id


def _chapter_id(job_id: str, position_index: int) -> UUID:
    """The id of the chapter at the given index of the position-sorted list."""
    return registry.status(job_id, OWNER).chapters[position_index].chapter_id


def _drive_to(job_id: str, status: BulkJobStatus) -> None:
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


@pytest.fixture(autouse=True)
def _clear_jobs() -> None:
    """Registry state is process-global — every test starts empty."""
    registry._JOBS.clear()


class TestOwnership:
    """foreign ≡ unknown → identical NotFoundError (anti-enumeration, §6)."""

    def test_unknown_id_raises_not_found_with_registry_message(self) -> None:
        with pytest.raises(NotFoundError, match="Bulk extraction job 'missing' not found"):
            registry.status("missing", OWNER)

    def test_foreign_user_message_is_identical_to_unknown(self) -> None:
        """Same template, same 404 — the message must not reveal ownership."""
        job_id = _make_job(0, 1)
        with pytest.raises(NotFoundError) as foreign_exc:
            registry.status(job_id, FOREIGN)
        with pytest.raises(NotFoundError) as unknown_exc:
            registry.status("missing", FOREIGN)
        assert str(foreign_exc.value) == f"Bulk extraction job '{job_id}' not found"
        assert str(unknown_exc.value) == "Bulk extraction job 'missing' not found"

    def test_foreign_user_rejected_on_every_user_facing_op(self) -> None:
        job_id = _make_job(0)
        message = re.escape(f"Bulk extraction job '{job_id}' not found")
        with pytest.raises(NotFoundError, match=message):
            registry.results(job_id, FOREIGN)
        with pytest.raises(NotFoundError, match=message):
            registry.request_cancel(job_id, FOREIGN)
        with pytest.raises(NotFoundError, match=message):
            registry.reset_for_resume(job_id, FOREIGN)

    def test_owner_still_has_access(self) -> None:
        job_id = _make_job(0)
        assert registry.status(job_id, OWNER).job_id == job_id
        assert registry.results(job_id, OWNER).job_id == job_id


class TestLifecycle:
    def test_create_starts_pending_with_full_totals(self) -> None:
        job = registry.create(NOVEL_ID, OWNER, [_ref(0), _ref(1), _ref(2)])
        assert job.status is BulkJobStatus.PENDING
        assert (job.totals.total, job.totals.done, job.totals.failed, job.totals.remaining) == (
            3,
            0,
            0,
            3,
        )
        assert job.error is None
        assert job.created_at <= job.updated_at

    def test_create_sorts_chapters_by_position(self) -> None:
        job_id = _make_job(5, 1, 3)
        positions = [c.position for c in registry.status(job_id, OWNER).chapters]
        assert positions == [1, 3, 5]

    def test_full_walk_to_completed(self) -> None:
        job_id = _make_job(0, 1, 2)
        ids = [_chapter_id(job_id, i) for i in range(3)]

        registry.mark_job_running(job_id)
        assert registry.status(job_id, OWNER).status is BulkJobStatus.RUNNING

        registry.mark_chapter_running(job_id, ids[0])
        rows = registry.status(job_id, OWNER)
        assert rows.chapters[0].state is BulkChapterState.RUNNING
        assert rows.totals.remaining == 3  # running chapters stay remaining

        out = _output(4)
        registry.mark_chapter_done(job_id, ids[0], out)
        rows = registry.status(job_id, OWNER)
        assert rows.chapters[0].state is BulkChapterState.DONE
        assert rows.chapters[0].item_count == 4
        assert rows.totals.done == 1
        assert rows.totals.remaining == 2

        result_rows = registry.results(job_id, OWNER).chapters
        assert result_rows[0].output == out
        assert result_rows[1].output is None  # not done → no output (iff invariant)

        registry.mark_chapter_done(job_id, ids[1], _output(0))
        registry.mark_chapter_done(job_id, ids[2], _output(2))
        registry.mark_job_completed(job_id)
        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.COMPLETED
        assert (job.totals.done, job.totals.failed, job.totals.remaining) == (3, 0, 0)
        assert job.updated_at >= job.created_at

    def test_zero_item_output_is_a_valid_done(self) -> None:
        job_id = _make_job(0)
        registry.mark_chapter_done(job_id, _chapter_id(job_id, 0), _output(0))
        row = registry.status(job_id, OWNER).chapters[0]
        assert row.state is BulkChapterState.DONE
        assert row.item_count == 0


class TestMarkNoOps:
    """mark_* / runner helpers are job-id-keyed no-ops-with-warning on unknown ids."""

    def test_every_mark_and_helper_on_unknown_job_neither_raises_nor_creates(self) -> None:
        registry.mark_job_running("missing")
        registry.mark_chapter_running("missing", uuid4())
        registry.mark_chapter_done("missing", uuid4(), _output(1))
        registry.mark_chapter_failed("missing", uuid4(), "boom")
        registry.mark_job_completed("missing")
        registry.mark_job_failed("missing", "boom")
        registry.mark_cancelled("missing", "cancelled (server shutdown)")
        assert registry._JOBS == {}
        assert registry.cancel_requested("missing") is False
        assert registry.pending_chapter_ids("missing") == []
        assert registry.find_active_for_novel(NOVEL_ID) is None

    def test_unknown_chapter_inside_a_known_job_is_a_noop(self) -> None:
        job_id = _make_job(0, 1)
        registry.mark_job_running(job_id)
        registry.mark_chapter_running(job_id, uuid4())
        registry.mark_chapter_failed(job_id, uuid4(), "boom")
        rows = registry.status(job_id, OWNER)
        assert rows.status is BulkJobStatus.RUNNING
        assert [c.state for c in rows.chapters] == [
            BulkChapterState.PENDING,
            BulkChapterState.PENDING,
        ]


class TestCancel:
    def test_request_cancel_sets_cancelling_and_flag(self) -> None:
        job_id = _make_job(0)
        registry.mark_job_running(job_id)
        job = registry.request_cancel(job_id, OWNER)
        assert job.status is BulkJobStatus.CANCELLING
        assert registry.cancel_requested(job_id) is True

    @pytest.mark.parametrize("terminal", _TERMINAL)
    def test_request_cancel_on_terminal_conflicts(self, terminal: BulkJobStatus) -> None:
        job_id = _make_job(0)
        _drive_to(job_id, terminal)
        with pytest.raises(ConflictError, match="terminal"):
            registry.request_cancel(job_id, OWNER)

    def test_mark_cancelled_is_terminal_with_visible_reason(self) -> None:
        job_id = _make_job(0)
        registry.request_cancel(job_id, OWNER)
        registry.mark_cancelled(job_id, "cancelled (server shutdown)")
        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.CANCELLED
        assert job.error == "cancelled (server shutdown)"


class TestResume:
    def test_resume_from_cancelled_resets_non_done_keeps_done(self) -> None:
        job_id = _make_job(0, 1, 2)
        ids = [_chapter_id(job_id, i) for i in range(3)]
        registry.mark_job_running(job_id)
        out = _output(7)
        registry.mark_chapter_done(job_id, ids[0], out)
        registry.mark_chapter_failed(job_id, ids[1], "agent timed out")
        registry.request_cancel(job_id, OWNER)
        registry.mark_cancelled(job_id, "cancelled by user")

        job = registry.reset_for_resume(job_id, OWNER)
        assert job.status is BulkJobStatus.PENDING
        assert job.error is None

        rows = registry.status(job_id, OWNER).chapters
        assert [c.state for c in rows] == [
            BulkChapterState.DONE,
            BulkChapterState.PENDING,
            BulkChapterState.PENDING,
        ]
        assert rows[0].item_count == 7  # done output + item_count retained
        assert rows[1].error is None  # stale failure reason cleared on re-pend
        assert registry.results(job_id, OWNER).chapters[0].output == out
        assert registry.cancel_requested(job_id) is False  # must not self-cancel again

        totals = registry.status(job_id, OWNER).totals
        assert (totals.done, totals.failed, totals.remaining) == (1, 0, 2)
        assert registry.pending_chapter_ids(job_id) == [ids[1], ids[2]]  # position order

    def test_resume_from_failed_resets_failed_chapter_and_clears_job_error(self) -> None:
        job_id = _make_job(0)
        registry.mark_job_failed(job_id, "NO_AI_PROVIDER")
        job = registry.reset_for_resume(job_id, OWNER)
        assert job.status is BulkJobStatus.PENDING
        assert job.error is None
        assert registry.status(job_id, OWNER).chapters[0].state is BulkChapterState.PENDING

    def test_resume_covers_a_running_chapter_stranded_by_drain(self) -> None:
        job_id = _make_job(0)
        chapter = _chapter_id(job_id, 0)
        registry.mark_job_running(job_id)
        registry.mark_chapter_running(job_id, chapter)
        registry.mark_cancelled(job_id, "cancelled (server shutdown)")  # drain kills it mid-flight

        registry.reset_for_resume(job_id, OWNER)
        assert registry.pending_chapter_ids(job_id) == [chapter]  # not lost, not stuck running

    @pytest.mark.parametrize("status", _NOT_RESUMABLE)
    def test_resume_from_non_resumable_conflicts(self, status: BulkJobStatus) -> None:
        job_id = _make_job(0)
        _drive_to(job_id, status)
        with pytest.raises(ConflictError):
            registry.reset_for_resume(job_id, OWNER)


class TestFailureIsolation:
    def test_chapter_failure_records_error_job_stays_running(self) -> None:
        job_id = _make_job(0, 1)
        ids = [_chapter_id(job_id, i) for i in range(2)]
        registry.mark_job_running(job_id)

        registry.mark_chapter_failed(job_id, ids[0], "agent call timed out")
        rows = registry.status(job_id, OWNER)
        assert rows.status is BulkJobStatus.RUNNING  # job continues (spec §5)
        assert rows.chapters[0].state is BulkChapterState.FAILED
        assert rows.chapters[0].error == "agent call timed out"
        assert rows.chapters[0].item_count is None
        assert rows.totals.failed == 1
        assert rows.totals.remaining == 1  # only the still-pending chapter

    def test_job_failure_is_terminal_with_reason(self) -> None:
        job_id = _make_job(0)
        registry.mark_job_running(job_id)
        registry.mark_job_failed(job_id, "NO_AI_PROVIDER")
        job = registry.status(job_id, OWNER)
        assert job.status is BulkJobStatus.FAILED
        assert job.error == "NO_AI_PROVIDER"
        assert job.totals.remaining == 1


class TestSweep:
    @pytest.fixture(autouse=True)
    def _frozen_now(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Free time in BOTH modules (each binds its own ``_now``/``utc_now`` name)."""
        monkeypatch.setattr(registry, "_now", lambda: _FROZEN_NOW)
        monkeypatch.setattr(registry_store, "utc_now", lambda: _FROZEN_NOW)

    @staticmethod
    def _sweeper(hours_after_now: float) -> Callable[[], datetime]:
        return lambda: _FROZEN_NOW + timedelta(hours=hours_after_now)

    @pytest.mark.parametrize("terminal", _TERMINAL)
    def test_terminal_job_swept_only_after_ttl(self, terminal: BulkJobStatus) -> None:
        job_id = _make_job(0)
        _drive_to(job_id, terminal)
        assert registry.sweep_expired(now=self._sweeper(1)) == 0  # inside the 24 h TTL
        assert registry.status(job_id, OWNER).job_id == job_id
        assert registry.sweep_expired(now=self._sweeper(25)) == 1  # BULK_JOB_TTL elapsed
        with pytest.raises(NotFoundError):
            registry.status(job_id, OWNER)

    def test_running_job_never_swept(self) -> None:
        job_id = _make_job(0)
        registry.mark_job_running(job_id)
        assert registry.sweep_expired(now=self._sweeper(10_000)) == 0
        assert registry.status(job_id, OWNER).status is BulkJobStatus.RUNNING

    def test_pending_job_never_swept(self) -> None:
        job_id = _make_job(0)
        assert registry.sweep_expired(now=self._sweeper(10_000)) == 0
        assert registry.status(job_id, OWNER).status is BulkJobStatus.PENDING

    def test_ttl_is_the_contract_constant(self) -> None:
        assert BULK_JOB_TTL.total_seconds() == 24 * 3600


class TestActiveScan:
    def test_running_job_is_found(self) -> None:
        job_id = _make_job(0, 1)
        registry.mark_job_running(job_id)
        assert registry.find_active_for_novel(NOVEL_ID) == job_id

    @pytest.mark.parametrize("active", [BulkJobStatus.PENDING, BulkJobStatus.CANCELLING])
    def test_pending_and_cancelling_count_as_active(self, active: BulkJobStatus) -> None:
        job_id = _make_job(0)
        _drive_to(job_id, active)
        assert registry.find_active_for_novel(NOVEL_ID) == job_id

    def test_only_terminal_jobs_are_not_active(self) -> None:
        for terminal in _TERMINAL:
            _drive_to(_make_job(0), terminal)
        assert registry.find_active_for_novel(NOVEL_ID) is None

    def test_other_novels_job_is_not_matched(self) -> None:
        _make_job(0)
        assert registry.find_active_for_novel(uuid4()) is None


class TestPendingChapterIds:
    def test_position_order_snapshot_isolation(self) -> None:
        job_id = _make_job(5, 1, 3)
        ids = registry.pending_chapter_ids(job_id)
        assert ids == [c.chapter_id for c in registry.status(job_id, OWNER).chapters]
        ids.append(uuid4())  # mutating the returned list must not touch the registry
        assert len(registry.pending_chapter_ids(job_id)) == 3

    def test_only_pending_chapters_are_listed(self) -> None:
        job_id = _make_job(0, 1, 2)
        ids = [_chapter_id(job_id, i) for i in range(3)]
        registry.mark_job_running(job_id)
        registry.mark_chapter_done(job_id, ids[0], _output(1))
        registry.mark_chapter_running(job_id, ids[1])
        assert registry.pending_chapter_ids(job_id) == [ids[2]]
