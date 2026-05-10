"""Unit tests for chapters/service.py"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from narrare.chapters.models import Chapter
from narrare.chapters.schemas import UpdateChapterContentRequest
from narrare.chapters.service import ChapterService


def _make_chapter(**kwargs: object) -> Chapter:
    from sqlalchemy.orm.attributes import set_attribute

    chapter = Chapter()
    set_attribute(chapter, "id", kwargs.get("id", uuid.uuid4()))
    set_attribute(chapter, "novel_id", kwargs.get("novel_id", uuid.uuid4()))
    set_attribute(chapter, "title", kwargs.get("title", "Test Chapter"))
    set_attribute(chapter, "content", kwargs.get("content", ""))
    set_attribute(chapter, "position", kwargs.get("position", 0))
    set_attribute(chapter, "word_count", kwargs.get("word_count", 0))
    set_attribute(chapter, "status", "draft")
    set_attribute(chapter, "pov_character_id", "")
    set_attribute(chapter, "timeline_position", "")
    set_attribute(chapter, "embeddings_dirty", True)
    return chapter


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(mock_session: MagicMock) -> ChapterService:
    svc = ChapterService(mock_session)
    # Mock the novel service ownership check
    svc._novel_service.get = AsyncMock(return_value=MagicMock())  # type: ignore[reportPrivateUsage]
    return svc


class TestChapterServiceUpdateContent:
    async def test_raises_413_for_oversized_content(self, service: ChapterService) -> None:
        novel_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        user_id = uuid.uuid4()

        service._repo.get_by_id = AsyncMock(return_value=_make_chapter())  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.update_content(
                chapter_id,
                novel_id,
                user_id,
                UpdateChapterContentRequest(content="x" * 100_001),
            )
        assert exc.value.status_code == 413

    async def test_computes_word_count_when_not_provided(self, service: ChapterService) -> None:
        novel_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        user_id = uuid.uuid4()
        chapter = _make_chapter()

        service._repo.get_by_id = AsyncMock(return_value=chapter)  # type: ignore[reportPrivateUsage]
        service._repo.update_content = AsyncMock(return_value=chapter)  # type: ignore[reportPrivateUsage]

        await service.update_content(
            chapter_id,
            novel_id,
            user_id,
            UpdateChapterContentRequest(content="five words are in here"),
        )

        service._repo.update_content.assert_called_once()  # type: ignore[reportPrivateUsage, reportAttributeAccessIssue]
        _, _, word_count_arg = service._repo.update_content.call_args.args  # type: ignore[reportAttributeAccessIssue]
        assert word_count_arg == 5

    async def test_raises_404_when_chapter_not_found(self, service: ChapterService) -> None:
        service._repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.update_content(
                uuid.uuid4(),
                uuid.uuid4(),
                uuid.uuid4(),
                UpdateChapterContentRequest(content="content"),
            )
        assert exc.value.status_code == 404
