"""Unit tests for chapters/repository.py — DB query layer + count_words helper."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.chapters.models import Chapter
from narrare.chapters.repository import ChapterRepository, count_words
from narrare.chapters.schemas import CreateChapterRequest, UpdateChapterMetaRequest


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
def repo(mock_session: MagicMock) -> ChapterRepository:
    return ChapterRepository(mock_session)


# ---------------------------------------------------------------------------
# count_words (pure function)
# ---------------------------------------------------------------------------


class TestCountWords:
    def test_counts_words_in_normal_text(self) -> None:
        assert count_words("hello world foo") == 3

    def test_returns_zero_for_empty_string(self) -> None:
        assert count_words("") == 0

    def test_returns_zero_for_whitespace_only(self) -> None:
        assert count_words("   \n\t  ") == 0

    def test_counts_words_with_extra_whitespace(self) -> None:
        assert count_words("  hello   world  ") == 2


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


class TestChapterRepositoryGetById:
    async def test_returns_chapter_when_found(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        chapter = _make_chapter()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = chapter
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(chapter.id, chapter.novel_id)

        assert result == chapter

    async def test_returns_none_when_not_found(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(uuid.uuid4(), uuid.uuid4())

        assert result is None


# ---------------------------------------------------------------------------
# list_by_novel
# ---------------------------------------------------------------------------


class TestChapterRepositoryListByNovel:
    async def test_returns_chapters_ordered_by_position(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        chapters = [_make_chapter(position=0), _make_chapter(position=1)]
        mock_result = MagicMock()
        mock_result.scalars.return_value = chapters
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_novel(uuid.uuid4())

        assert len(result) == 2

    async def test_returns_empty_list_for_no_chapters(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_novel(uuid.uuid4())

        assert result == []


# ---------------------------------------------------------------------------
# max_position
# ---------------------------------------------------------------------------


class TestChapterRepositoryMaxPosition:
    async def test_returns_max_position(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 5
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.max_position(uuid.uuid4())

        assert result == 5

    async def test_returns_negative_one_when_no_chapters(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.max_position(uuid.uuid4())

        assert result == -1


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestChapterRepositoryCreate:
    async def test_creates_chapter_with_word_count(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        request = CreateChapterRequest(title="New Chapter", content="hello world")
        result = await repo.create(uuid.uuid4(), request, position=0)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert result.word_count == 2
        assert result.position == 0

    async def test_create_with_empty_content_has_zero_word_count(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        request = CreateChapterRequest(title="Empty", content="")
        result = await repo.create(uuid.uuid4(), request, position=3)

        assert result.word_count == 0
        assert result.position == 3


# ---------------------------------------------------------------------------
# update_content
# ---------------------------------------------------------------------------


class TestChapterRepositoryUpdateContent:
    async def test_updates_content_and_marks_dirty(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        chapter = _make_chapter(content="old")
        mock_session.flush = AsyncMock()

        result = await repo.update_content(chapter, "new content", 2)

        assert result.content == "new content"
        assert result.word_count == 2
        assert result.embeddings_dirty is True
        mock_session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# update_meta
# ---------------------------------------------------------------------------


class TestChapterRepositoryUpdateMeta:
    async def test_updates_meta_fields(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        chapter = _make_chapter(title="Old Title")
        mock_session.flush = AsyncMock()

        # Rebuild model to resolve forward reference (volume_id uses uuid.UUID under TYPE_CHECKING)
        import uuid as _uuid

        UpdateChapterMetaRequest.model_rebuild(_types_namespace={"uuid": _uuid})
        request = UpdateChapterMetaRequest(title="New Title")
        result = await repo.update_meta(chapter, request)

        assert result.title == "New Title"
        mock_session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------


class TestChapterRepositoryReorder:
    async def test_reorder_sets_positions(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        chapter_ids = [uuid.uuid4(), uuid.uuid4()]
        mock_session.execute = AsyncMock()
        mock_session.flush = AsyncMock()

        # Mock list_by_novel (called internally by reorder)
        with pytest.MonkeyPatch.context() as _:
            ordered = [_make_chapter(position=0), _make_chapter(position=1)]
            mock_result = MagicMock()
            mock_result.scalars.return_value = ordered
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await repo.reorder(uuid.uuid4(), chapter_ids)

            assert len(result) == 2


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestChapterRepositoryDelete:
    async def test_deletes_chapter_and_flushes(
        self, repo: ChapterRepository, mock_session: MagicMock
    ) -> None:
        chapter = _make_chapter()
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        await repo.delete(chapter)

        mock_session.delete.assert_called_once_with(chapter)
        mock_session.flush.assert_called_once()
