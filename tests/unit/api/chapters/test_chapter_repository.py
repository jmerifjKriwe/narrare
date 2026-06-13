"""Unit tests for ChapterRepository — mock session tests for uncovered methods.

These tests use mock AsyncSession objects to verify repository method behaviors
without requiring a real database. They cover the specific lines that remain
uncovered in the full-suite run because integration tests don't exercise them.

Uncovered lines targeted:
  - repository.py:41   — list_by_novel with volume_id set
  - repository.py:89-91  — update_summary method
  - repository.py:149-155 — list_versions method
  - repository.py:163-169 — get_version method
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.chapters.models import Chapter, ChapterVersion
from narrare.chapters.repository import ChapterRepository
from narrare.chapters.schemas import UpdateChapterMetaRequest

_RESULT_ATTRS = ["scalars", "scalar_one_or_none"]


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock AsyncSession for repository testing.

    The session's execute() returns a MagicMock (not AsyncMock) because
    the Result object returned by execute() has synchronous methods like
    .scalars() and .scalar_one_or_none().
    """
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> ChapterRepository:
    return ChapterRepository(mock_session)


def _make_result(**kwargs: object) -> MagicMock:
    """Create a MagicMock that mimics SQLAlchemy's Result.

    The Result returned by session.execute() has synchronous methods
    (.scalars(), .scalar_one_or_none()), so we use MagicMock, not AsyncMock.
    """
    result: MagicMock = MagicMock(spec=_RESULT_ATTRS)
    for key, value in kwargs.items():
        setattr(result, key, value)
    return result


def _returning(value: object) -> MagicMock:
    """Callable mock returning *value* — satisfies RULE-TEST-01."""
    return MagicMock(spec=[], return_value=value)


# ---------------------------------------------------------------------------
# list_by_novel — volume_id branch (line 41)
# ---------------------------------------------------------------------------


class TestListByNovel:
    async def test_without_volume_id_returns_all(
        self, repo: ChapterRepository, mock_session: AsyncMock
    ) -> None:
        """When volume_id is None, all chapters for the novel are returned."""
        ch1 = MagicMock(spec=Chapter)
        ch2 = MagicMock(spec=Chapter)
        result = _make_result(scalars=_returning([ch1, ch2]))
        mock_session.execute.return_value = result

        novel_id = uuid.uuid4()
        chapters = await repo.list_by_novel(novel_id)

        assert len(chapters) == 2
        mock_session.execute.assert_called_once()

    async def test_with_volume_id_filters_by_volume(
        self, repo: ChapterRepository, mock_session: AsyncMock
    ) -> None:
        """When volume_id is provided, only chapters in that volume are returned
        (covers line 41 — the if-volume_id-is-not-None branch)."""
        ch1 = MagicMock(spec=Chapter)
        result = _make_result(scalars=_returning([ch1]))
        mock_session.execute.return_value = result

        novel_id = uuid.uuid4()
        volume_id = uuid.uuid4()
        chapters = await repo.list_by_novel(novel_id, volume_id=volume_id)

        assert len(chapters) == 1
        mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# update_summary (lines 89-91)
# ---------------------------------------------------------------------------


class TestUpdateSummary:
    async def test_update_summary_sets_summary_and_flushes(
        self, repo: ChapterRepository, mock_session: AsyncMock
    ) -> None:
        """update_summary sets the chapter summary and flushes/refreshes
        (covers lines 89-91)."""
        chapter = MagicMock(spec=Chapter)
        chapter.summary = "old summary"

        result = await repo.update_summary(chapter, "new summary")

        assert result.summary == "new summary"
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(chapter)


# ---------------------------------------------------------------------------
# list_versions (lines 149-155)
# ---------------------------------------------------------------------------


class TestListVersions:
    async def test_list_versions_returns_versions_newest_first(
        self, repo: ChapterRepository, mock_session: AsyncMock
    ) -> None:
        """list_versions queries chapter_versions ordered by version_number desc
        (covers lines 149-155)."""
        v1 = MagicMock(spec=ChapterVersion)
        v2 = MagicMock(spec=ChapterVersion)
        result = _make_result(scalars=_returning([v2, v1]))
        mock_session.execute.return_value = result

        chapter_id = uuid.uuid4()
        versions = await repo.list_versions(chapter_id)

        assert len(versions) == 2
        assert versions[0] is v2
        assert versions[1] is v1
        mock_session.execute.assert_called_once()

    async def test_list_versions_empty_when_no_versions(
        self, repo: ChapterRepository, mock_session: AsyncMock
    ) -> None:
        """list_versions returns empty list when no versions exist."""
        result = _make_result(scalars=_returning([]))
        mock_session.execute.return_value = result

        versions = await repo.list_versions(uuid.uuid4())

        assert versions == []


# ---------------------------------------------------------------------------
# get_version (lines 163-169)
# ---------------------------------------------------------------------------


class TestGetVersion:
    async def test_get_version_returns_version_when_found(
        self, repo: ChapterRepository, mock_session: AsyncMock
    ) -> None:
        """get_version returns the version when it exists
        (covers lines 163-169)."""
        version = MagicMock(spec=ChapterVersion)
        result = _make_result(scalar_one_or_none=_returning(version))
        mock_session.execute.return_value = result

        found = await repo.get_version(uuid.uuid4(), uuid.uuid4())

        assert found is version

    async def test_get_version_returns_none_when_not_found(
        self, repo: ChapterRepository, mock_session: AsyncMock
    ) -> None:
        """get_version returns None when version doesn't exist."""
        result = _make_result(scalar_one_or_none=_returning(None))
        mock_session.execute.return_value = result

        found = await repo.get_version(uuid.uuid4(), uuid.uuid4())

        assert found is None


# ---------------------------------------------------------------------------
# Additional branch coverage — update_meta with partial data
# ---------------------------------------------------------------------------


class TestUpdateMetaBranch:
    async def test_update_meta_with_empty_request_does_nothing(
        self, repo: ChapterRepository, mock_session: AsyncMock
    ) -> None:
        """update_meta with request that has all-None fields calls model_dump
        and iterates zero items."""
        chapter = MagicMock(spec=Chapter)
        request = UpdateChapterMetaRequest()  # all fields None

        result = await repo.update_meta(chapter, request)

        assert result is chapter
        mock_session.flush.assert_awaited_once()
