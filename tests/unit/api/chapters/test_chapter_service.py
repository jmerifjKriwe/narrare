"""Unit tests for chapters/service.py"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from narrare.chapters.models import Chapter
from narrare.chapters.schemas import (
    CreateChapterRequest,
    UpdateChapterContentRequest,
    UpdateChapterMetaRequest,
)
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


class TestChapterServiceGet:
    async def test_get_returns_chapter_when_found(self, service: ChapterService) -> None:
        chapter = _make_chapter()
        service._repo.get_by_id = AsyncMock(return_value=chapter)  # type: ignore[reportPrivateUsage]

        result = await service.get(chapter.id, chapter.novel_id, uuid.uuid4())

        assert result == chapter

    async def test_get_raises_404_when_not_found(self, service: ChapterService) -> None:
        service._repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.get(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404


class TestChapterServiceList:
    async def test_list_returns_chapters_for_novel(self, service: ChapterService) -> None:
        chapters = [_make_chapter(), _make_chapter()]
        service._repo.list_by_novel = AsyncMock(return_value=chapters)  # type: ignore[reportPrivateUsage]

        result = await service.list_chapters(uuid.uuid4(), uuid.uuid4())

        assert len(result) == 2


class TestChapterServiceCreate:
    async def test_create_with_explicit_position(self, service: ChapterService) -> None:
        chapter = _make_chapter(position=5)
        service._repo.create = AsyncMock(return_value=chapter)  # type: ignore[reportPrivateUsage]

        request = CreateChapterRequest(title="New Chapter", content="hello", position=5)
        result = await service.create(uuid.uuid4(), uuid.uuid4(), request)

        assert result == chapter
        service._repo.create.assert_called_once()  # type: ignore[reportPrivateUsage]

    async def test_create_appends_at_end_when_no_position(self, service: ChapterService) -> None:
        chapter = _make_chapter(position=3)
        service._repo.max_position = AsyncMock(return_value=2)  # type: ignore[reportPrivateUsage]
        service._repo.create = AsyncMock(return_value=chapter)  # type: ignore[reportPrivateUsage]

        request = CreateChapterRequest(title="Appended", content="text")
        result = await service.create(uuid.uuid4(), uuid.uuid4(), request)

        assert result == chapter


class TestChapterServiceUpdateMeta:
    async def test_update_meta_modifies_chapter(self, service: ChapterService) -> None:
        chapter = _make_chapter(title="Old Title")
        updated = _make_chapter(id=chapter.id, title="New Title")
        service._repo.get_by_id = AsyncMock(return_value=chapter)  # type: ignore[reportPrivateUsage]
        service._repo.update_meta = AsyncMock(return_value=updated)  # type: ignore[reportPrivateUsage]

        # Rebuild model to resolve forward reference
        import uuid as _uuid

        UpdateChapterMetaRequest.model_rebuild(_types_namespace={"uuid": _uuid})

        result = await service.update_meta(
            chapter.id,
            chapter.novel_id,
            uuid.uuid4(),
            UpdateChapterMetaRequest(title="New Title"),
        )

        assert result.title == "New Title"


class TestChapterServiceReorder:
    async def test_reorder_calls_repo(self, service: ChapterService) -> None:
        chapter_ids = [uuid.uuid4(), uuid.uuid4()]
        reordered = [_make_chapter(), _make_chapter()]
        service._repo.reorder = AsyncMock(return_value=reordered)  # type: ignore[reportPrivateUsage]

        result = await service.reorder(uuid.uuid4(), uuid.uuid4(), chapter_ids)

        assert len(result) == 2


class TestChapterServiceDelete:
    async def test_delete_removes_chapter(self, service: ChapterService) -> None:
        chapter = _make_chapter()
        service._repo.get_by_id = AsyncMock(return_value=chapter)  # type: ignore[reportPrivateUsage]
        service._repo.delete = AsyncMock()  # type: ignore[reportPrivateUsage]

        await service.delete(chapter.id, chapter.novel_id, uuid.uuid4())

        service._repo.delete.assert_called_once_with(chapter)  # type: ignore[reportPrivateUsage]

    async def test_delete_raises_404_when_not_found(self, service: ChapterService) -> None:
        service._repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.delete(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404
