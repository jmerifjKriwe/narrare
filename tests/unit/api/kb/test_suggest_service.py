"""Unit tests for KBSuggestService.

Tests the API-layer wrapper that resolves chapter content and entity
metadata, then delegates to ProactiveContextService.

Uses fakes for all three dependencies (proactive context, chapter repo, KB repo).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Literal, cast

import pytest

from narrare.kb.schemas import KBSuggestionResponse
from narrare.kb.suggest_service import KBSuggestService
from narrare_core.context.suggestion import EntityMetadata, Suggestion
from narrare_core.shared.errors import NotFoundError

from ._test_fakes import FakeNovelRepo

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.novels.contracts import NovelRepositoryProtocol

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeChapter:
    """Minimal chapter-like object for tests."""

    def __init__(self, content: str = "Chapter text here.") -> None:
        self.id = uuid.uuid4()
        self.content = content


class FakeKBEntry:
    """Minimal KB entry-like object for tests."""

    def __init__(
        self,
        name: str = "Aria",
        entity_type: str = "character",
        usage_count: int = 0,
        last_referenced_at: datetime | None = None,
    ) -> None:
        self.id = uuid.uuid4()
        self.name = name
        self.entity_type = entity_type
        self.usage_count = usage_count
        self.last_referenced_at = last_referenced_at


class FakeProactiveContext:
    """Fake ProactiveContextProtocol for tests."""

    def __init__(self, suggestions: list[Suggestion] | None = None) -> None:
        self._suggestions = suggestions or []
        self.last_max_results: int | None = None

    async def suggest(
        self,
        chapter_content: str,
        *,
        novel_id: UUID,
        chapter_frontmatter: dict[str, object] | None = None,
        entity_names: list[str] | None = None,
        max_results: int = 20,
        entity_metadata: dict[UUID, EntityMetadata] | None = None,
    ) -> list[Suggestion]:
        self.last_max_results = max_results
        return self._suggestions


class FakeChapterRepo:
    """Fake ChapterRepositoryProtocol for tests."""

    def __init__(self, chapter: FakeChapter | None = None) -> None:
        self._chapter = chapter

    async def get_by_id(self, chapter_id: UUID, novel_id: UUID) -> FakeChapter | None:
        return self._chapter


class FakeKBRepo:
    """Fake KBRepositoryProtocol for tests."""

    def __init__(self, entries: list[FakeKBEntry] | None = None) -> None:
        self._entries = entries or []

    async def list_entries(
        self,
        novel_id: UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[FakeKBEntry], int]:
        return self._entries, len(self._entries)


def _make_suggestion(
    entry_id: UUID | None = None,
    name: str = "Aria",
    entry_type: str = "character",
    relevance_score: float = 0.85,
    reason: Literal[
        "mentioned_in_text", "semantically_similar", "recently_used"
    ] = "mentioned_in_text",
    similarity: float = 0.75,
    usage_count: int = 3,
    last_referenced_at: datetime | None = None,
) -> Suggestion:
    return Suggestion(
        entry_id=entry_id or uuid.uuid4(),
        entry_type=entry_type,
        name=name,
        relevance_score=relevance_score,
        reason=reason,
        similarity=similarity,
        usage_count=usage_count,
        last_referenced_at=last_referenced_at,
    )


# ---------------------------------------------------------------------------
# Service factory (centralizes type: ignore for incomplete test fakes)
# ---------------------------------------------------------------------------


_SENTINEL = object()


def _make_service(
    proactive: FakeProactiveContext | None = None,
    chapter: FakeChapter | None = _SENTINEL,  # type: ignore[assignment]
    entries: list[FakeKBEntry] | None = None,
) -> KBSuggestService:
    """Create a KBSuggestService with fake dependencies.

    By default, a FakeChapter is provided so the service finds a chapter.
    Pass chapter=None explicitly to test the "not found" path.

    The novel-ownership gate (IDOR fix S9) is permissive by default —
    ownership behavior is covered by
    ``test_graph_suggest_consistency_ownership.py``.
    """
    resolved_chapter = FakeChapter() if chapter is _SENTINEL else chapter
    return KBSuggestService(
        proactive_context=proactive or FakeProactiveContext(),
        chapter_repo=FakeChapterRepo(resolved_chapter),  # type: ignore[arg-type]
        kb_repo=FakeKBRepo(entries),  # type: ignore[arg-type]
        novel_repo=cast("NovelRepositoryProtocol", FakeNovelRepo()),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetSuggestionsSuccess:
    """Happy path: proactive returns suggestions, repos return data."""

    async def test_returns_response_objects(self) -> None:
        """Service maps Suggestion → KBSuggestionResponse correctly."""
        entry_id = uuid.uuid4()
        last_ref = datetime(2026, 5, 20, 12, 0, 0)
        suggestions = [
            _make_suggestion(
                entry_id=entry_id,
                name="Aria",
                relevance_score=0.85,
                reason="mentioned_in_text",
                similarity=0.75,
                usage_count=3,
                last_referenced_at=last_ref,
            ),
        ]

        service = _make_service(
            proactive=FakeProactiveContext(suggestions),
            chapter=FakeChapter(content="Aria entered the room."),
            entries=[FakeKBEntry(name="Aria")],
        )

        result = await service.get_suggestions(
            chapter_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

        assert len(result) == 1
        assert isinstance(result[0], KBSuggestionResponse)
        assert result[0].entry_id == entry_id
        assert result[0].name == "Aria"
        assert result[0].reason == "mentioned_in_text"
        assert result[0].last_referenced_at == last_ref


class TestGetSuggestionsChapterNotFound:
    """Chapter None → raises NotFoundError (IDOR fix S9, foreign ≡ unknown)."""

    async def test_raises_not_found_error(self) -> None:
        """Service raises NotFoundError when the chapter is not in the novel.

        Formerly a ``ValueError`` (500-shaped); the S9 compound gate
        makes chapter∉novel indistinguishable from an unknown chapter
        (404) — same shape as the writing-module suggest gate (S6).
        """
        service = _make_service(chapter=None)  # chapter not found

        chapter_id = uuid.uuid4()

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.get_suggestions(
                chapter_id=chapter_id,
                novel_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
            )


class TestGetSuggestionsEmptyKB:
    """No entries → empty entity_names/metadata passed to proactive."""

    async def test_empty_kb_passes_empty_metadata(self) -> None:
        """Service passes empty entity_names when KB has no entries."""
        service = _make_service(
            proactive=FakeProactiveContext(suggestions=[]),
            chapter=FakeChapter(content="Some text."),
            entries=[],
        )

        result = await service.get_suggestions(
            chapter_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

        assert result == []


class TestGetSuggestionsMaxResultsPassedThrough:
    """max_results parameter is forwarded to proactive context."""

    async def test_max_results_forwarded(self) -> None:
        """Service passes max_results to proactive.suggest()."""
        fake_proactive = FakeProactiveContext(suggestions=[])

        service = _make_service(proactive=fake_proactive, chapter=FakeChapter())

        await service.get_suggestions(
            chapter_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            max_results=5,
        )

        assert fake_proactive.last_max_results == 5


class TestGetSuggestionsMapsToResponse:
    """Suggestion fields → KBSuggestionResponse with rounding."""

    async def test_relevance_score_rounded(self) -> None:
        """Relevance score is rounded to 4 decimal places."""
        suggestions = [
            _make_suggestion(relevance_score=0.85123456, similarity=0.75987654),
        ]

        service = _make_service(proactive=FakeProactiveContext(suggestions))

        result = await service.get_suggestions(
            chapter_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

        assert result[0].relevance_score == 0.8512
        assert result[0].similarity == 0.7599

    async def test_multiple_suggestions_preserved_in_order(self) -> None:
        """Multiple suggestions are mapped in order."""
        suggestions = [
            _make_suggestion(name="Aria", relevance_score=0.9),
            _make_suggestion(name="Castle", relevance_score=0.7),
            _make_suggestion(name="Sword", relevance_score=0.5),
        ]

        service = _make_service(proactive=FakeProactiveContext(suggestions))

        result = await service.get_suggestions(
            chapter_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

        assert len(result) == 3
        assert result[0].name == "Aria"
        assert result[1].name == "Castle"
        assert result[2].name == "Sword"


# TestDefaultMaxResultsConstant extracted to test_suggest_constant.py (RULE-04)
