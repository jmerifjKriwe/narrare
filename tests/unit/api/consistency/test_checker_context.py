"""Unit tests for ``collect_check_context`` — KB relationship wiring (FIND-001).

Verifies that the consistency context builder fetches KB relationships and
populates ``ConsistencyDeps.kb_relationships`` when a ``RelationshipRepository``
is provided and ``include_kb`` is set. Also covers graceful degradation
(repo=None or include_kb=False) per RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from narrare.consistency.checker_context import collect_check_context
from narrare.consistency.schemas import ConsistencyRequest
from narrare.kb.relationship_repository import RelationshipEdgeRow
from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api._test_helpers import make_chapter, make_novel, seed_repos

if TYPE_CHECKING:
    from narrare.novels.models import Novel


def _build_repos() -> tuple[Novel, FakeNovelRepository, FakeChapterRepository]:
    """Return (novel, novel_repo, chapter_repo) seeded for context collection."""
    novel = make_novel()
    chapter = make_chapter(novel_id=novel.id)
    nr, cr = FakeNovelRepository(), FakeChapterRepository()
    seed_repos(novel, chapter, novel_repo=nr, chapter_repo=cr)
    return novel, nr, cr


def _mock_kb_repo() -> AsyncMock:
    kb = AsyncMock()
    kb.list_entries = AsyncMock(return_value=([], 0))
    return kb


def _mock_timeline_repo() -> AsyncMock:
    timeline = AsyncMock()
    timeline.list_by_novel = AsyncMock(return_value=[])
    return timeline


def _mock_relationship_repo(*, edges: list[RelationshipEdgeRow] | None = None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_relationships_with_names = AsyncMock(return_value=edges or [])
    return repo


class TestCollectCheckContextRelationships:
    """collect_check_context populates deps.kb_relationships (CR-AUFG-03-01)."""

    @pytest.mark.asyncio
    async def test_fetches_relationships_when_repo_and_include_kb(self) -> None:
        """Relationships are fetched and formatted when repo is provided + include_kb."""
        novel, nr, cr = _build_repos()
        rel_repo = _mock_relationship_repo(
            edges=[
                RelationshipEdgeRow("Aria", "enemy_of", "ancient feud", "Malachai", "directed"),
            ]
        )

        context = await collect_check_context(
            novel.id,
            novel.user_id,
            ConsistencyRequest(chapter_ids=[], include_kb=True),
            chapter_repo=cr,
            novel_repo=nr,
            kb_repo=_mock_kb_repo(),
            timeline_repo=_mock_timeline_repo(),
            relationship_repo=rel_repo,
        )

        rel_repo.get_relationships_with_names.assert_awaited_once_with(novel_id=novel.id)
        # format_relationships renders the label → "Aria → [ancient feud] → Malachai"
        assert context.deps.kb_relationships == "Aria → [ancient feud] → Malachai"

    @pytest.mark.asyncio
    async def test_empty_relationships_when_repo_none(self) -> None:
        """No relationship_repo → deps.kb_relationships stays empty (graceful degradation)."""
        novel, nr, cr = _build_repos()

        context = await collect_check_context(
            novel.id,
            novel.user_id,
            ConsistencyRequest(chapter_ids=[], include_kb=True),
            chapter_repo=cr,
            novel_repo=nr,
            kb_repo=_mock_kb_repo(),
            timeline_repo=_mock_timeline_repo(),
        )

        assert context.deps.kb_relationships == ""

    @pytest.mark.asyncio
    async def test_empty_relationships_when_include_kb_false(self) -> None:
        """include_kb=False → relationships are not fetched, deps.kb_relationships empty."""
        novel, nr, cr = _build_repos()
        rel_repo = _mock_relationship_repo(
            edges=[
                RelationshipEdgeRow("Aria", "ally_of", None, "Thane", "mutual"),
            ]
        )

        context = await collect_check_context(
            novel.id,
            novel.user_id,
            ConsistencyRequest(chapter_ids=[], include_kb=False),
            chapter_repo=cr,
            novel_repo=nr,
            kb_repo=_mock_kb_repo(),
            timeline_repo=_mock_timeline_repo(),
            relationship_repo=rel_repo,
        )

        rel_repo.get_relationships_with_names.assert_not_awaited()
        assert context.deps.kb_relationships == ""

    @pytest.mark.asyncio
    async def test_relationships_empty_when_no_edges(self) -> None:
        """Repo returns no edges → deps.kb_relationships is empty string."""
        novel, nr, cr = _build_repos()
        rel_repo = _mock_relationship_repo(edges=[])

        context = await collect_check_context(
            novel.id,
            novel.user_id,
            ConsistencyRequest(chapter_ids=[], include_kb=True),
            chapter_repo=cr,
            novel_repo=nr,
            kb_repo=_mock_kb_repo(),
            timeline_repo=_mock_timeline_repo(),
            relationship_repo=rel_repo,
        )

        assert context.deps.kb_relationships == ""
