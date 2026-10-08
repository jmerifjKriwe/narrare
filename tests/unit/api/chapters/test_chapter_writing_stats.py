"""Unit tests — ChapterService x WritingStatsRecorder wiring (STATS-001, E3a).

The editor content-update and version-restore surfaces must call the
recorder exactly once per successful write with the correct SIGNED delta.
Delta math is computed BEFORE the repo write because repositories update
the chapter row in place — the old word count is unrecoverable afterwards.
Zero deltas are pinned as a call WITH 0 (skipping is the recorder's
internal job, ADR-095). Delete, the never-raises failure posture, and the
optional-DI backward compatibility live in
``test_chapter_writing_stats_delete.py`` (RULE-04 file-size split).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from narrare.chapters.schemas import UpdateChapterContentRequest
from narrare.chapters.service import ChapterService
from narrare_core.shared.errors import NotFoundError
from tests.factories import make_chapter
from tests.fakes import FakeChapterRepository, FakeNovelService, FakeWritingStatsRecorder
from tests.unit.api.chapters._writing_stats_test_helpers import (
    assert_single_call,
    seed_chapter,
    seed_ownership,
)

if TYPE_CHECKING:
    from narrare.chapters.models import Chapter, ChapterVersion


# ---------------------------------------------------------------------------
# Fixtures
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
# update_content (editor PATCH)
# ---------------------------------------------------------------------------


class TestUpdateContentRecordsDelta:
    async def test_update_content_with_growth_records_positive_delta(
        self,
        service: ChapterService,
        recorder: FakeWritingStatsRecorder,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = seed_ownership(fake_novel_service)
        chapter = seed_chapter(fake_repo, novel_id, word_count=2)

        await service.update_content(
            chapter.id,
            novel_id,
            user_id,
            UpdateChapterContentRequest(content="one two three four five"),
        )

        assert_single_call(
            recorder,
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter.id,
            delta_words=3,  # 5 new - 2 old
        )

    async def test_update_content_with_shrink_records_negative_delta(
        self,
        service: ChapterService,
        recorder: FakeWritingStatsRecorder,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = seed_ownership(fake_novel_service)
        chapter = seed_chapter(fake_repo, novel_id, word_count=50)

        await service.update_content(
            chapter.id,
            novel_id,
            user_id,
            UpdateChapterContentRequest(content="only four words now"),
        )

        assert_single_call(
            recorder,
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter.id,
            delta_words=-46,  # 4 new - 50 old
        )

    async def test_update_content_with_identical_count_records_zero_delta_call(
        self,
        service: ChapterService,
        recorder: FakeWritingStatsRecorder,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """Zero delta is still CALLED WITH 0 — the skip is the recorder's job."""
        novel_id, user_id = seed_ownership(fake_novel_service)
        chapter = seed_chapter(fake_repo, novel_id, word_count=5)

        await service.update_content(
            chapter.id,
            novel_id,
            user_id,
            UpdateChapterContentRequest(content="one two three four five"),
        )

        assert_single_call(
            recorder,
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter.id,
            delta_words=0,
        )

    async def test_update_content_with_missing_chapter_records_nothing(
        self,
        service: ChapterService,
        recorder: FakeWritingStatsRecorder,
        fake_novel_service: FakeNovelService,
    ) -> None:
        """A failed write (404) must not emit a stats event."""
        novel_id, user_id = seed_ownership(fake_novel_service)

        with pytest.raises(NotFoundError):
            await service.update_content(
                uuid.uuid4(),
                novel_id,
                user_id,
                UpdateChapterContentRequest(content="content"),
            )

        assert recorder.calls == []


# ---------------------------------------------------------------------------
# restore_version
# ---------------------------------------------------------------------------


class TestRestoreVersionRecordsDelta:
    async def _seed_version_to_restore(
        self,
        fake_repo: FakeChapterRepository,
        novel_id: uuid.UUID,
        *,
        version_word_count: int,
        version_content: str,
        current_word_count: int,
    ) -> tuple[Chapter, ChapterVersion]:
        """Chapter at CURRENT state; version 1 snapshotted at the old state."""
        chapter = make_chapter(
            novel_id=novel_id,
            content=version_content,
            word_count=version_word_count,
        )
        fake_repo.seed(chapter)
        version = await fake_repo.save_version(chapter, 1)
        # Simulate later edits: chapter has drifted from the snapshotted version.
        chapter.content = "totally different current words here"
        chapter.word_count = current_word_count
        return chapter, version

    async def test_restore_version_to_shorter_content_records_negative_delta(
        self,
        service: ChapterService,
        recorder: FakeWritingStatsRecorder,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = seed_ownership(fake_novel_service)
        chapter, version = await self._seed_version_to_restore(
            fake_repo,
            novel_id,
            version_word_count=5,
            version_content="one two three four five",
            current_word_count=120,
        )

        await service.restore_version(chapter.id, version.id, novel_id, user_id)

        assert_single_call(
            recorder,
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter.id,
            delta_words=-115,  # 5 restored - 120 current
        )

    async def test_restore_version_to_identical_content_records_zero_delta_call(
        self,
        service: ChapterService,
        recorder: FakeWritingStatsRecorder,
        fake_repo: FakeChapterRepository,
        fake_novel_service: FakeNovelService,
    ) -> None:
        novel_id, user_id = seed_ownership(fake_novel_service)
        chapter, version = await self._seed_version_to_restore(
            fake_repo,
            novel_id,
            version_word_count=5,
            version_content="one two three four five",
            current_word_count=5,
        )

        await service.restore_version(chapter.id, version.id, novel_id, user_id)

        assert_single_call(
            recorder,
            user_id=user_id,
            novel_id=novel_id,
            chapter_id=chapter.id,
            delta_words=0,
        )
