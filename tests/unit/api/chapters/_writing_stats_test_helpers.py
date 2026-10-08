"""Shared helpers for the ChapterService x WritingStatsRecorder test modules.

Used by ``test_chapter_writing_stats.py`` (editor update + version restore)
and ``test_chapter_writing_stats_delete.py`` (delete + failure posture) —
STATS-001 E3a. Fixtures are declared locally in each test module (house
pattern); only the plain seeding/assertion helpers live here.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from tests.factories import make_chapter, make_novel

if TYPE_CHECKING:
    from narrare.chapters.models import Chapter
    from tests.fakes import FakeChapterRepository, FakeNovelService, FakeWritingStatsRecorder


class _ExplodingSessionFactory:
    """Stands in for ``async_sessionmaker`` — every session open fails.

    Shared by the never-raises posture pins (real ``SqlWritingStatsRecorder``
    behind a failing session factory — a raising fake would contradict the
    contract): delete/update in ``test_chapter_writing_stats_delete.py``,
    create in ``test_chapter_writing_stats.py`` (fix round).
    """

    def __call__(self, *args: Any) -> _ExplodingSessionCtx:
        return _ExplodingSessionCtx()


class _ExplodingSessionCtx:
    def __enter__(self) -> _ExplodingSessionCtx:
        raise RuntimeError("db down")

    def __aenter__(self) -> _ExplodingSessionCtx:
        raise RuntimeError("db down")

    def __aexit__(self, *args: Any) -> None:
        del args


def seed_ownership(fake_novel_service: FakeNovelService) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a novel into the fake novel service for ownership checks."""
    novel_id, user_id = uuid.uuid4(), uuid.uuid4()
    fake_novel_service.seed(make_novel(id=novel_id, user_id=user_id))
    return novel_id, user_id


def seed_chapter(
    fake_repo: FakeChapterRepository,
    novel_id: uuid.UUID,
    *,
    word_count: int,
) -> Chapter:
    """Seed one chapter with the given word count into the fake repo."""
    chapter = make_chapter(novel_id=novel_id, word_count=word_count)
    fake_repo.seed(chapter)
    return chapter


def assert_single_call(
    recorder: FakeWritingStatsRecorder,
    *,
    user_id: uuid.UUID,
    novel_id: uuid.UUID,
    chapter_id: uuid.UUID,
    delta_words: int,
) -> None:
    """Exactly one recorder call with the fully attributed signed delta."""
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["user_id"] == user_id
    assert call["novel_id"] == novel_id
    assert call["chapter_id"] == chapter_id
    assert call["delta_words"] == delta_words
