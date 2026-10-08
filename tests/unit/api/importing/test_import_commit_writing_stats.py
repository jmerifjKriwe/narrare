"""Unit tests — ImportService.commit x WritingStatsRecorder (STATS-001 E3b).

Commit emits exactly ONE signed positive delta per IMPORTED chapter
(excluded chapters emit nothing), each stamped with that chapter's NEW id
and word count plus the committing user/novel — no attribution leaks
between commits. The never-raises posture is pinned with the REAL
``SqlWritingStatsRecorder`` behind an exploding session factory: a stats
capture failure must never fail the import (ADR-095). Day-of-import
attribution needs no call-site work — the recorder stamps ``created_at``
from its clock at write time (ADR-095 D1, no backdating).
"""

from __future__ import annotations

import io
import uuid
from typing import TYPE_CHECKING, cast

from fastapi import UploadFile
from starlette.datastructures import Headers

from narrare.analytics.writing_stats_recorder import SqlWritingStatsRecorder
from narrare.chapters.models import Chapter
from narrare.importing.schemas import ImportCommitAdjustments
from narrare.importing.service import ImportService
from narrare.novels.models import Novel
from tests.fakes import FakeWritingStatsRecorder
from tests.fakes.fake_db_session import FakeDbSession
from tests.fakes.fake_novel_repo import FakeNovelRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from narrare_core.importing.models import DetectedChapter

NOVEL_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data),
        size=len(data),
        filename=name,
        headers=Headers({"content-type": "application/octet-stream"}),
    )


class _FakeChapterRepo:
    """Structurally satisfies ImportChapterRepositoryProtocol — keeps rows."""

    def __init__(self) -> None:
        self.rows: list[Chapter] = []

    async def max_position(self, novel_id: uuid.UUID) -> int:
        return 0

    async def append_chapters(
        self,
        novel_id: uuid.UUID,
        chapters: Sequence[DetectedChapter],
        start_position: int,
    ) -> list[Chapter]:
        # Mirror the real repository contract: return the created rows
        # (ids generated client-side by the model default) — these are the
        # identities the recorder calls must carry.
        self.rows = [
            Chapter(
                # Explicit ids: the real repository flushes, and the model's
                # uuid default is applied at INSERT — unflushed instances
                # carry id=None. The service reads row.id right after the
                # append, so the fake must mirror the flushed contract.
                id=uuid.uuid4(),
                novel_id=novel_id,
                title=chapter.title,
                content=chapter.content,
                position=start_position + offset,
                word_count=chapter.word_count,
                status=chapter.status,
            )
            for offset, chapter in enumerate(chapters)
        ]
        return self.rows


def _service(
    recorder: FakeWritingStatsRecorder | SqlWritingStatsRecorder | None = None,
    *,
    novel_id: uuid.UUID = NOVEL_ID,
    user_id: uuid.UUID = USER_ID,
) -> tuple[ImportService, _FakeChapterRepo]:
    repo = _FakeChapterRepo()
    novel_repo = FakeNovelRepository()
    novel_repo.seed(Novel(id=novel_id, user_id=user_id, title="Import Target"))
    return (
        ImportService(
            session=cast("AsyncSession", FakeDbSession()),  # commit never touches the session
            chapter_repo=repo,
            novel_repo=novel_repo,
            writing_stats_recorder=recorder,
        ),
        repo,
    )


def _files() -> list[UploadFile]:
    # Fresh streams per call — UploadFile.read() consumes its buffer, so a
    # shared module-level constant would leak empty files between tests.
    # "body one" ⇒ 2 words, "body two three" ⇒ 3 words (headings are titles).
    return [
        _upload("a.md", b"# One\nbody one"),
        _upload("b.md", b"# Two\nbody two three"),
    ]


class TestCommitRecordsPerChapterDeltas:
    async def test_one_event_per_imported_chapter_with_per_chapter_attribution(
        self,
    ) -> None:
        """Two imported chapters ⇒ exactly two calls; each carries ITS OWN
        row id and word count (per-chapter events, never a bulk total)."""
        recorder = FakeWritingStatsRecorder()
        service, repo = _service(recorder)

        result = await service.commit(_files(), NOVEL_ID, USER_ID, ImportCommitAdjustments())

        assert result.created_count == 2
        assert len(recorder.calls) == 2
        assert repo.rows[0].id != repo.rows[1].id  # distinct chapter identities
        assert {row.word_count for row in repo.rows} == {2, 3}
        for row, call in zip(repo.rows, recorder.calls, strict=True):
            assert call["user_id"] == USER_ID
            assert call["novel_id"] == NOVEL_ID
            assert call["chapter_id"] == row.id
            assert call["delta_words"] == row.word_count

    async def test_excluded_chapter_records_no_event(self) -> None:
        """Only IMPORTED chapters emit events — an excluded index yields
        exactly one call, for the surviving chapter."""
        recorder = FakeWritingStatsRecorder()
        service, repo = _service(recorder)

        result = await service.commit(
            _files(), NOVEL_ID, USER_ID, ImportCommitAdjustments(excluded_indices=[1])
        )

        assert result.created_count == 1
        assert len(recorder.calls) == 1
        assert recorder.calls[0]["chapter_id"] == repo.rows[0].id
        assert recorder.calls[0]["delta_words"] == repo.rows[0].word_count
        assert recorder.calls[0]["novel_id"] == NOVEL_ID


class TestCommitAttributionIsolation:
    async def test_attribution_does_not_leak_between_novels_or_users(self) -> None:
        """Two commits (different novels AND users) through ONE shared
        recorder ⇒ every event is stamped with its own commit's identity."""
        novel_a, user_a = uuid.uuid4(), uuid.uuid4()
        novel_b, user_b = uuid.uuid4(), uuid.uuid4()
        recorder = FakeWritingStatsRecorder()
        service_a, repo_a = _service(recorder, novel_id=novel_a, user_id=user_a)
        service_b, repo_b = _service(recorder, novel_id=novel_b, user_id=user_b)

        await service_a.commit(_files(), novel_a, user_a, ImportCommitAdjustments())
        await service_b.commit(_files(), novel_b, user_b, ImportCommitAdjustments())

        # Two chapters per commit ⇒ four events, partitioned strictly by
        # commit: the first block belongs entirely to novel A/user A, the
        # second entirely to novel B/user B.
        assert len(recorder.calls) == 4
        assert [(call["novel_id"], call["user_id"]) for call in recorder.calls] == [
            (novel_a, user_a),
            (novel_a, user_a),
            (novel_b, user_b),
            (novel_b, user_b),
        ]
        assert [call["chapter_id"] for call in recorder.calls] == [
            repo_a.rows[0].id,
            repo_a.rows[1].id,
            repo_b.rows[0].id,
            repo_b.rows[1].id,
        ]


# ---------------------------------------------------------------------------
# Never-raises posture (real recorder behind a failing session factory)
# ---------------------------------------------------------------------------


class _ExplodingSessionFactory:
    """Stands in for ``async_sessionmaker`` — every session open fails."""

    def __call__(self, *args: object) -> _ExplodingSessionCtx:
        return _ExplodingSessionCtx()


class _ExplodingSessionCtx:
    def __enter__(self) -> _ExplodingSessionCtx:
        raise RuntimeError("db down")

    def __aenter__(self) -> _ExplodingSessionCtx:
        raise RuntimeError("db down")

    def __aexit__(self, *args: object) -> None:
        del args


class TestRecorderFailureDoesNotBreakCommit:
    async def test_commit_succeeds_when_recorder_persistence_fails(self) -> None:
        """Real SqlWritingStatsRecorder swallows the DB failure; the import
        commit completes with its full response (ADR-095 posture)."""
        recorder = SqlWritingStatsRecorder(
            # cast: the sanctioned seam for a fake where async_sessionmaker is declared.
            cast("async_sessionmaker[AsyncSession]", _ExplodingSessionFactory()),
        )
        service, _repo = _service(recorder)

        result = await service.commit(_files(), NOVEL_ID, USER_ID, ImportCommitAdjustments())

        assert result.created_count == 2  # import intact despite recorder failure
        assert [chapter.title for chapter in result.chapters] == ["One", "Two"]
