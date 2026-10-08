# tests/unit/api/analytics/test_writing_stats_recorder.py
"""Unit tests for ``SqlWritingStatsRecorder`` (STATS-001, ADR-095).

The recorder is the never-raises capture seam on the content-write path:
zero deltas skip before any session is opened, params map 1:1 onto the
``WritingActivityEventRow`` (``created_at`` = write-time clock — never DB
now()), one short-lived session per event with insert-then-commit via the
repository, and ANY persistence failure is swallowed with a warning —
unlike ``SqlUsageEventSink`` (whose caller, the Core emitter, is the
single guarded seam) the recorder itself must absorb failures because its
callers are content-write services with no outer guard. The repository
insert wiring is fake-session-tested here too (same split as
test_usage_record_repository.py); SQL semantics are proven against real
PostgreSQL by the 0045 round-trip test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from structlog.testing import capture_logs
from tests.fakes.fake_db_session import FakeDbSession

from narrare.analytics import writing_stats_recorder
from narrare.analytics.repository import WritingActivityEventRepository
from narrare.analytics.writing_models import WritingActivityEventRow
from narrare.analytics.writing_stats_recorder import (
    SqlWritingStatsRecorder,
    WritingStatsRecorder,
)

if TYPE_CHECKING:
    import pytest
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_NOW = datetime(2026, 10, 8, 12, 30, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fakes (ADR-030: real fakes, no MagicMock)
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal ``AsyncSession`` fake: records ``commit`` in the op log."""

    def __init__(self, ops: list[str], *, fail_commit: bool = False) -> None:
        self._ops = ops
        self._fail_commit = fail_commit

    async def commit(self) -> None:
        if self._fail_commit:
            raise RuntimeError("commit exploded")
        self._ops.append("commit")


class _FakeSessionCtx:
    """Async context manager — mirrors ``async with factory() as session``."""

    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        del args


class _FakeSessionFactory:
    """Stands in for ``async_sessionmaker[AsyncSession]``; logs session opens."""

    def __init__(self, ops: list[str], *, fail_commit: bool = False) -> None:
        self._ops = ops
        self._fail_commit = fail_commit
        self.opened = 0

    def __call__(self) -> _FakeSessionCtx:
        self._ops.append("open")
        self.opened += 1
        return _FakeSessionCtx(_FakeSession(self._ops, fail_commit=self._fail_commit))


class _Harness:
    """Recorder wired to fakes + captured bookkeeping (op log, inserted rows)."""

    def __init__(self, *, fail_commit: bool = False) -> None:
        self.ops: list[str] = []
        self.inserted: list[WritingActivityEventRow] = []
        self.factory = _FakeSessionFactory(self.ops, fail_commit=fail_commit)

    def recorder(self) -> SqlWritingStatsRecorder:
        return SqlWritingStatsRecorder(
            cast("async_sessionmaker[AsyncSession]", self.factory),
            clock=lambda: _NOW,
        )


def _recording_harness(monkeypatch: pytest.MonkeyPatch) -> _Harness:
    """Recorder whose repository is replaced by a recording fake."""

    class _FakeRepository:
        def __init__(self, session: _FakeSession) -> None:
            self.session = session

        async def insert_writing_event(self, row: WritingActivityEventRow) -> None:
            harness.inserted.append(row)
            harness.ops.append("insert")

    harness = _Harness()
    monkeypatch.setattr(writing_stats_recorder, "WritingActivityEventRepository", _FakeRepository)
    return harness


def _exploding_recorder(monkeypatch: pytest.MonkeyPatch) -> SqlWritingStatsRecorder:
    """Recorder whose repository insert always raises (failure-path tests)."""

    class _ExplodingRepository:
        def __init__(self, session: _FakeSession) -> None:
            del session

        async def insert_writing_event(self, row: WritingActivityEventRow) -> None:
            del row
            raise RuntimeError("db down")

    monkeypatch.setattr(
        writing_stats_recorder, "WritingActivityEventRepository", _ExplodingRepository
    )
    return SqlWritingStatsRecorder(
        cast("async_sessionmaker[AsyncSession]", _FakeSessionFactory([])),
        clock=lambda: _NOW,
    )


async def _record(
    recorder: WritingStatsRecorder,
    *,
    delta_words: int = 250,
    chapter_id: Any = ...,
) -> None:
    """One standard ``record_delta`` call (explicit attribution, no ContextVars)."""
    await recorder.record_delta(
        user_id=uuid4(),
        novel_id=uuid4(),
        chapter_id=uuid4() if chapter_id is ... else chapter_id,
        delta_words=delta_words,
    )


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


class TestSqlWritingStatsRecorder:
    async def test_zero_delta_skips_without_session_or_insert(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty creates / restores-to-identical produce no row (ADR-095)."""
        harness = _recording_harness(monkeypatch)

        with capture_logs() as logs:
            await _record(harness.recorder(), delta_words=0)

        assert harness.factory.opened == 0  # no session opened
        assert harness.inserted == []  # nothing persisted
        skipped = [entry for entry in logs if entry["event"] == "writing_stats_delta_skipped_zero"]
        assert len(skipped) == 1
        assert skipped[0]["log_level"] == "debug"

    async def test_positive_delta_maps_params_onto_row_and_commits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        harness = _recording_harness(monkeypatch)
        user_id, novel_id, chapter_id = uuid4(), uuid4(), uuid4()

        await harness.recorder().record_delta(
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter_id,
            delta_words=250,
        )

        assert harness.factory.opened == 1  # own short-lived session per event
        assert harness.ops == ["open", "insert", "commit"]  # commit after insert
        assert len(harness.inserted) == 1
        row = harness.inserted[0]
        assert row.user_id == user_id
        assert row.novel_id == novel_id
        assert row.chapter_id == chapter_id
        assert row.delta_words == 250
        assert row.created_at == _NOW  # write-time clock — no DB now(), no backdating

    async def test_negative_delta_is_persisted_signed_without_chapter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Chapter delete emits an honest negative delta; chapter_id is NULLable."""
        harness = _recording_harness(monkeypatch)

        await harness.recorder().record_delta(
            user_id=uuid4(), novel_id=uuid4(), chapter_id=None, delta_words=-140
        )

        assert harness.inserted[0].delta_words == -140
        assert harness.inserted[0].chapter_id is None

    async def test_repository_failure_is_swallowed_and_logged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Never-raises: a repo failure returns normally, warning logged once."""
        recorder = _exploding_recorder(monkeypatch)

        with capture_logs() as logs:
            await _record(recorder)  # must NOT raise

        failures = [entry for entry in logs if entry["event"] == "writing_stats_record_failed"]
        assert len(failures) == 1
        assert failures[0]["log_level"] == "warning"

    async def test_commit_failure_is_swallowed_and_logged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing commit is inside the same never-raises guard."""
        harness = _Harness(fail_commit=True)

        class _FakeRepository:
            def __init__(self, session: _FakeSession) -> None:
                del session

            async def insert_writing_event(self, row: WritingActivityEventRow) -> None:
                harness.inserted.append(row)
                harness.ops.append("insert")

        monkeypatch.setattr(
            writing_stats_recorder, "WritingActivityEventRepository", _FakeRepository
        )

        with capture_logs() as logs:
            await _record(harness.recorder())  # must NOT raise

        assert harness.ops == ["open", "insert"]  # insert ran, commit raised
        failures = [entry for entry in logs if entry["event"] == "writing_stats_record_failed"]
        assert len(failures) == 1
        assert failures[0]["log_level"] == "warning"

    async def test_recorder_satisfies_writing_stats_recorder_protocol(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Protocol conformance (RULE-03) — E3 call sites depend on this seam."""
        harness = _recording_harness(monkeypatch)

        assert isinstance(harness.recorder(), WritingStatsRecorder)


# ---------------------------------------------------------------------------
# Repository insert (fake-session wiring — house pattern)
# ---------------------------------------------------------------------------


class TestWritingActivityEventRepositoryInsert:
    async def test_insert_writing_event_adds_row_and_flushes_once_without_refresh(
        self,
    ) -> None:
        """Append + flush; no refresh (id is client-side, no server defaults)."""
        session = FakeDbSession()
        repo = WritingActivityEventRepository(cast("AsyncSession", session))
        row = WritingActivityEventRow(
            user_id=uuid4(),
            novel_id=uuid4(),
            chapter_id=None,
            delta_words=42,
            created_at=_NOW,
        )

        await repo.insert_writing_event(row)

        assert session.added == [row]
        assert session.flush_count == 1
        assert session.refreshed == []
