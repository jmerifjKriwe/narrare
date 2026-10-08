"""Unit tests — ChapterService x WritingStatsRecorder: delete + failure posture.

RULE-04 split from ``test_chapter_writing_stats.py`` (which owns the editor
update + version-restore surfaces). This module covers:

- chapter delete emits an honest NEGATIVE delta of the word count at delete
  time (net-words honesty, ADR-095 E-7), and a failed delete records nothing;
- the never-raises posture: pinned with the REAL ``SqlWritingStatsRecorder``
  behind an exploding session factory — a raising fake would contradict the
  contract, since call sites must not add try/except (the recorder is the
  single never-raises seam);
- backward compatibility: the recorder DI is optional, pre-existing
  constructions without it keep working.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

import pytest

from narrare.analytics.writing_stats_recorder import SqlWritingStatsRecorder
from narrare.chapters.schemas import UpdateChapterContentRequest
from narrare.chapters.service import ChapterService
from narrare_core.shared.errors import NotFoundError
from tests.fakes import FakeChapterRepository, FakeNovelService, FakeWritingStatsRecorder
from tests.unit.api.chapters._writing_stats_test_helpers import (
    assert_single_call,
    seed_chapter,
    seed_ownership,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# ---------------------------------------------------------------------------
# Fixtures (local — house pattern; helpers shared via _writing_stats_test_helpers)
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_repo() -> FakeChapterRepository:
    return FakeChapterRepository()


@pytest.fixture
def fake_novel_service() -> FakeNovelService:
    return FakeNovelService()


@pytest.fixture
def recorder() -> FakeWritingStatsRecorder:
    return FakeWritingStatsRecorder()


@pytest.fixture
def service(
    fake_repo: FakeChapterRepository,
    fake_novel_service: FakeNovelService,
    recorder: FakeWritingStatsRecorder,
) -> ChapterService:
    return ChapterService(
        repo=fake_repo,
        novel_service=fake_novel_service,
        writing_stats_recorder=recorder,
    )


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDeleteRecordsNegativeDelta:
    async def test_delete_records_negative_delta_of_deleted_word_count(
        self,
        service: ChapterService,
        recorder: FakeWritingStatsRecorder,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = seed_ownership(fake_novel_service)
        chapter = seed_chapter(fake_repo, novel_id, word_count=140)

        await service.delete(chapter.id, novel_id, user_id)

        assert_single_call(
            recorder,
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter.id,
            delta_words=-140,
        )

    async def test_delete_of_missing_chapter_records_nothing(
        self,
        service: ChapterService,
        recorder: FakeWritingStatsRecorder,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = seed_ownership(fake_novel_service)

        with pytest.raises(NotFoundError):
            await service.delete(uuid.uuid4(), novel_id, user_id)

        assert recorder.calls == []


# ---------------------------------------------------------------------------
# Never-raises posture (real recorder behind a failing session factory)
# ---------------------------------------------------------------------------


class _ExplodingSessionFactory:
    """Stands in for ``async_sessionmaker`` — every session open fails."""

    def __call__(self, *args: Any) -> _ExplodingSessionCtx:
        return _ExplodingSessionCtx()


class _ExplodingSessionCtx:
    def __enter__(self) -> _ExplodingSessionCtx:
        raise RuntimeError("db down")

    def __aenter__(self) -> _ExplodingSessionCtx:
        raise RuntimeError("db down")

    def __aexit__(self, *args: Any) -> None:
        del args


class TestRecorderFailureDoesNotBreakWrite:
    async def test_update_content_succeeds_when_recorder_persistence_fails(
        self,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """Real SqlWritingStatsRecorder swallows the DB failure; the save wins."""
        novel_id, user_id = seed_ownership(fake_novel_service)
        chapter = seed_chapter(fake_repo, novel_id, word_count=2)
        service = ChapterService(
            repo=fake_repo,
            novel_service=fake_novel_service,
            writing_stats_recorder=SqlWritingStatsRecorder(
                # cast: the sanctioned seam for a fake where async_sessionmaker is declared.
                cast("async_sessionmaker[AsyncSession]", _ExplodingSessionFactory()),
            ),
        )

        updated = await service.update_content(
            chapter.id,
            novel_id,
            user_id,
            UpdateChapterContentRequest(content="one two three four five"),
        )

        assert updated.word_count == 5  # write applied despite recorder failure


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


class TestOptionalRecorderDependency:
    async def test_service_without_recorder_still_writes_content(
        self,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """Existing constructions (no recorder) keep working — DI is optional."""
        novel_id, user_id = seed_ownership(fake_novel_service)
        chapter = seed_chapter(fake_repo, novel_id, word_count=2)
        service = ChapterService(repo=fake_repo, novel_service=fake_novel_service)

        updated = await service.update_content(
            chapter.id,
            novel_id,
            user_id,
            UpdateChapterContentRequest(content="one two three four five"),
        )

        assert updated.word_count == 5
