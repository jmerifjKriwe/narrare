"""Unit tests for ChapterWikiService — dependency propagation & schema.

Tests language/genre propagation to generation deps, empty content
handling, and response schema validation. Split from main test file
for RULE-04 compliance.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.chapters.contracts import ChapterRepositoryProtocol
from narrare.chapters.models import Chapter
from narrare.novels.contracts import NovelRepositoryProtocol
from narrare.novels.models import Novel
from narrare.wiki.chapter_service import ChapterWikiService
from narrare.wiki.repository import WikiRepository
from narrare_core.wiki.contracts import WikiServiceProtocol
from narrare_core.wiki.types import WikiChapterOutput, WikiGenerationDeps

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_NOVEL_ID = uuid.uuid4()
_CHAPTER_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_novel(**overrides: Any) -> MagicMock:
    """Create a mock Novel with test defaults."""
    novel = MagicMock(spec=Novel)
    novel.id = _NOVEL_ID
    novel.writing_language = "en"
    novel.genre = "Fantasy"
    for k, v in overrides.items():
        setattr(novel, k, v)
    return novel


def _make_chapter(**overrides: Any) -> MagicMock:
    """Create a mock Chapter with test defaults."""
    chapter = MagicMock(spec=Chapter)
    chapter.id = _CHAPTER_ID
    chapter.title = "The Crystal Cave"
    chapter.content = "Lyra and Eldrin descend into the crystal cave."
    for k, v in overrides.items():
        setattr(chapter, k, v)
    return chapter


def _make_chapter_output(**overrides: Any) -> WikiChapterOutput:
    """Create a WikiChapterOutput with test defaults."""
    return WikiChapterOutput(
        narrative_summary="Lyra and Eldrin descend into the cave and find a hidden portal.",
        key_events=["Descend into cave", "Find hidden portal"],
        entities_involved=[
            {"name": "Lyra", "role": "protagonist"},
            {"name": "Eldrin", "role": "mentor"},
        ],
        themes=["Discovery", "Courage"],
        emotional_arc="tense to triumphant",
        **overrides,
    )


def _make_persisted_chapter_summary() -> dict[str, Any]:
    """Return a dict that WikiChapterSummaryResponse.model_validate accepts."""
    now = datetime.now(UTC)
    return {
        "id": uuid.uuid4(),
        "chapter_id": _CHAPTER_ID,
        "narrative_summary": "Lyra and Eldrin descend into the cave and find a hidden portal.",
        "key_events": ["Descend into cave", "Find hidden portal"],
        "entities_involved": [
            {"name": "Lyra", "role": "protagonist"},
            {"name": "Eldrin", "role": "mentor"},
        ],
        "themes": ["Discovery", "Courage"],
        "emotional_arc": "tense to triumphant",
        "status": "fresh",
        "version": 1,
        "created_at": now,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_novel_repo() -> MagicMock:
    """Mock NovelRepositoryProtocol."""
    repo = MagicMock(spec=NovelRepositoryProtocol)
    repo.get = AsyncMock(return_value=_make_novel())
    repo.get_by_id = AsyncMock(return_value=_make_novel())
    return repo


@pytest.fixture()
def mock_chapter_repo() -> MagicMock:
    """Mock ChapterRepositoryProtocol."""
    repo = MagicMock(spec=ChapterRepositoryProtocol)
    repo.get_by_id = AsyncMock(return_value=_make_chapter())
    return repo


@pytest.fixture()
def mock_wiki_repo() -> MagicMock:
    """Mock WikiRepository."""
    repo = MagicMock(spec=WikiRepository)
    repo.upsert_chapter_summary = AsyncMock(return_value=_make_persisted_chapter_summary())
    return repo


@pytest.fixture()
def mock_core() -> MagicMock:
    """Mock core WikiServiceProtocol (generate_chapter)."""
    core = MagicMock(spec=WikiServiceProtocol)
    core.generate_chapter = AsyncMock(return_value=_make_chapter_output())
    return core


@pytest.fixture()
def service(
    mock_wiki_repo: MagicMock,
    mock_novel_repo: MagicMock,
    mock_chapter_repo: MagicMock,
    mock_core: MagicMock,
) -> ChapterWikiService:
    """ChapterWikiService with all mocked deps — system_mode=False."""
    return ChapterWikiService(
        wiki_repo=mock_wiki_repo,
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        core_wiki_service=mock_core,
        system_mode=False,
    )


# ---------------------------------------------------------------------------
# Tests: dependency propagation and schema validation
# ---------------------------------------------------------------------------


class TestGenerateChapterSummaryDeps:
    """ChapterWikiService.generate_chapter_summary — deps & schema."""

    async def test_uses_novel_language_and_genre(
        self,
        service: ChapterWikiService,
        mock_novel_repo: MagicMock,
        mock_core: MagicMock,
    ) -> None:
        """Novel-level language and genre propagate to generation deps."""
        novel = _make_novel(writing_language="de", genre="Sci-Fi")
        mock_novel_repo.get_by_id.return_value = novel

        await service.generate_chapter_summary(_CHAPTER_ID, _NOVEL_ID, _USER_ID)

        call_deps: WikiGenerationDeps = mock_core.generate_chapter.call_args[1]["deps"]
        assert call_deps.language == "de"
        assert call_deps.genre == "Sci-Fi"

    async def test_handles_empty_content(
        self,
        service: ChapterWikiService,
        mock_chapter_repo: MagicMock,
        mock_core: MagicMock,
    ) -> None:
        """Chapter with empty content still generates deps correctly."""
        chapter = _make_chapter(content="")
        mock_chapter_repo.get_by_id.return_value = chapter

        await service.generate_chapter_summary(_CHAPTER_ID, _NOVEL_ID, _USER_ID)

        call_deps: WikiGenerationDeps = mock_core.generate_chapter.call_args[1]["deps"]
        assert call_deps.entity_body == ""
        assert call_deps.chapter_context == [""]

    async def test_response_schema_validation(
        self,
        service: ChapterWikiService,
        mock_wiki_repo: MagicMock,
    ) -> None:
        """Returns a valid WikiChapterSummaryResponse with correct fields."""
        result = await service.generate_chapter_summary(_CHAPTER_ID, _NOVEL_ID, _USER_ID)

        assert result is not None
        # Verify it's a proper schema with expected fields
        assert result.id is not None
        assert result.chapter_id == _CHAPTER_ID
        assert result.status == "fresh"
        assert result.version == 1
