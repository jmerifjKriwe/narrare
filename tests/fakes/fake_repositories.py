"""Backward-compatible re-exports — prefer importing from tests.fakes directly."""

from tests.fakes._shared import CallRecord
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_volume_repo import FakeVolumeRepository

__all__ = [
    "CallRecord",
    "FakeChapterRepository",
    "FakeNovelRepository",
    "FakeVolumeRepository",
]
