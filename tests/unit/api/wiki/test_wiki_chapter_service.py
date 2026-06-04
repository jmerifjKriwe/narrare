"""Unit tests for ChapterWikiService — chapter wiki summary generation.

Tests the generate_chapter_summary flow:
- Happy path with system_mode on/off
- Error cases (novel not found, chapter not found, generation failure)
- ForbiddenError propagation from ownership checks
- Graceful degradation (RULE-11)

All dependencies are mocked — no DB, no LLM.
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
from narrare_core.shared.errors import ForbiddenError
from narrare_core.wiki.contracts import WikiServiceProtocol
from narrare_core.wiki.types import WikiChapterOutput, WikiGenerationDeps

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_NOVEL_ID = uuid.uuid4()
_CHAPTER_ID = uuid.uuid4()


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
    """ChapterWikiService with all mocked deps — system_mode=False (user-facing)."""
    return ChapterWikiService(
        wiki_repo=mock_wiki_repo,
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        core_wiki_service=mock_core,
        system_mode=False,
    )


@pytest.fixture()
def system_service(
    mock_wiki_repo: MagicMock,
    mock_novel_repo: MagicMock,
    mock_chapter_repo: MagicMock,
    mock_core: MagicMock,
) -> ChapterWikiService:
    """ChapterWikiService with system_mode=True (bypasses ownership)."""
    return ChapterWikiService(
        wiki_repo=mock_wiki_repo,
        novel_repo=mock_novel_repo,
        chapter_repo=mock_chapter_repo,
        core_wiki_service=mock_core,
        system_mode=True,
    )


# ---------------------------------------------------------------------------
# Tests: generate_chapter_summary
# ---------------------------------------------------------------------------


class TestGenerateChapterSummary:
    """ChapterWikiService.generate_chapter_summary tests."""

    async def test_happy_path_user_mode(
        self,
        service: ChapterWikiService,
        mock_novel_repo: MagicMock,
        mock_chapter_repo: MagicMock,
        mock_core: MagicMock,
        mock_wiki_repo: MagicMock,
    ) -> None:
        """Happy path: loads novel via get_by_id, generates, persists, returns response."""
        result = await service.generate_chapter_summary(_CHAPTER_ID, _NOVEL_ID, _USER_ID)

        # Ownership check used get_by_id (not get)
        mock_novel_repo.get_by_id.assert_called_once_with(_NOVEL_ID, _USER_ID)
        mock_novel_repo.get.assert_not_called()

        # Chapter was loaded
        mock_chapter_repo.get_by_id.assert_called_once_with(_CHAPTER_ID, _NOVEL_ID)

        # Core generation was called with proper deps
        mock_core.generate_chapter.assert_called_once()
        call_deps: WikiGenerationDeps = mock_core.generate_chapter.call_args[1]["deps"]
        assert call_deps.entity_type == "chapter"
        assert call_deps.entity_name == "The Crystal Cave"
        assert call_deps.language == "en"
        assert call_deps.genre == "Fantasy"

        # Result persisted
        mock_wiki_repo.upsert_chapter_summary.assert_called_once()

        # Response returned
        assert result is not None
        assert (
            result.narrative_summary
            == "Lyra and Eldrin descend into the cave and find a hidden portal."
        )
        assert result.key_events is not None
        assert "Find hidden portal" in result.key_events

    async def test_system_mode_bypasses_ownership(
        self,
        system_service: ChapterWikiService,
        mock_novel_repo: MagicMock,
    ) -> None:
        """system_mode=True uses novel_repo.get() instead of get_by_id()."""
        result = await system_service.generate_chapter_summary(_CHAPTER_ID, _NOVEL_ID, _USER_ID)

        mock_novel_repo.get.assert_called_once_with(_NOVEL_ID)
        mock_novel_repo.get_by_id.assert_not_called()
        assert result is not None

    async def test_forbidden_error_propagates(
        self,
        service: ChapterWikiService,
        mock_novel_repo: MagicMock,
    ) -> None:
        """ForbiddenError from _load_novel propagates (not caught by generic handler)."""
        mock_novel_repo.get_by_id.return_value = None

        with pytest.raises(ForbiddenError, match="You do not have access to this novel"):
            await service.generate_chapter_summary(_CHAPTER_ID, _NOVEL_ID, _USER_ID)

    async def test_chapter_not_found_returns_none(
        self,
        service: ChapterWikiService,
        mock_chapter_repo: MagicMock,
        mock_core: MagicMock,
    ) -> None:
        """Returns None when chapter does not exist — no generation attempted."""
        mock_chapter_repo.get_by_id.return_value = None

        result = await service.generate_chapter_summary(_CHAPTER_ID, _NOVEL_ID, _USER_ID)

        assert result is None
        mock_core.generate_chapter.assert_not_called()

    async def test_generation_failure_returns_none(
        self,
        service: ChapterWikiService,
        mock_core: MagicMock,
        mock_wiki_repo: MagicMock,
    ) -> None:
        """Returns None when core generation returns None (graceful degradation)."""
        mock_core.generate_chapter.return_value = None

        result = await service.generate_chapter_summary(_CHAPTER_ID, _NOVEL_ID, _USER_ID)

        assert result is None
        mock_wiki_repo.upsert_chapter_summary.assert_not_called()

    async def test_exception_in_generation_returns_none(
        self,
        service: ChapterWikiService,
        mock_core: MagicMock,
    ) -> None:
        """Runtime error in core generation is caught — returns None (RULE-11)."""
        mock_core.generate_chapter.side_effect = RuntimeError("LLM timeout")

        result = await service.generate_chapter_summary(_CHAPTER_ID, _NOVEL_ID, _USER_ID)

        assert result is None

    async def test_exception_in_persist_returns_none(
        self,
        service: ChapterWikiService,
        mock_wiki_repo: MagicMock,
    ) -> None:
        """DB error on persist is caught — returns None (RULE-11)."""
        mock_wiki_repo.upsert_chapter_summary.side_effect = RuntimeError("DB connection lost")

        result = await service.generate_chapter_summary(_CHAPTER_ID, _NOVEL_ID, _USER_ID)

        assert result is None
