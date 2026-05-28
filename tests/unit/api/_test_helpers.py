"""Test-specific helpers for sentiment and consistency service tests."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

from tests.fakes._shared import _apply_setattr


def make_novel(**overrides: object):
    """Create a Novel model instance with sensible defaults."""
    from narrare.novels.models import Novel

    novel = Novel()
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "user_id": uuid4(),
        "title": "Test Novel",
        "writing_language": "en",
    }
    defaults.update(overrides)
    _apply_setattr(novel, defaults)
    return novel


def make_chapter(novel_id: uuid.UUID | None = None, **overrides: object):
    """Create a Chapter model instance with sensible defaults."""
    from narrare.chapters.models import Chapter

    nid = novel_id or uuid4()
    chapter = Chapter()
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "novel_id": nid,
        "title": "Test Chapter",
        "content": "She felt a surge of joy. The sun was shining brightly.",
        "position": 0,
        "word_count": 12,
    }
    defaults.update(overrides)
    _apply_setattr(chapter, defaults)
    return chapter


def make_kb_entry(novel_id: uuid.UUID, **overrides: object):
    """Create a KBEntry model instance with sensible defaults."""
    from narrare.kb.models import KBEntry

    entry = KBEntry()
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "novel_id": novel_id,
        "entity_type": "character",
        "name": "Anna",
        "slug": "anna",
        "metadata_": {"traits": ["brave"]},
    }
    defaults.update(overrides)
    _apply_setattr(entry, defaults)
    return entry


def make_mock_analyzer(return_value: object) -> AsyncMock:
    """Create a mock analyzer with an async analyze method."""
    return AsyncMock(analyze=AsyncMock(return_value=return_value))


def seed_repos(novel, *chapters, novel_repo, chapter_repo):
    """Seed fake repos with novel and chapters."""
    novel_repo.seed(novel)
    chapter_repo.seed(*chapters)
