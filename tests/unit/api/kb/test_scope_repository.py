"""Unit tests for KBRepository scope-aware *query* methods.

Series Foundation Spec 1, Task 2.2 — KB scope queries (read path).

Covers ``find_canon_for_series``, ``find_overlay_for_novel`` and
``find_merged_for_novel``. Mutation tests (promote/demote) live in
``test_scope_repository_mutations.py`` (RULE-04 file-size split).

Uses a mock ``AsyncSession`` (ADR-030 fakes pattern). Because the methods
construct Core Pydantic types from ORM rows, mocks return real ``KBEntry``
instances — see ``_scope_repo_helpers``.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.kb.repository import KBRepository
from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry
from tests.unit.api.kb._scope_repo_helpers import make_kb_model, make_result


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock AsyncSession for repository testing."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> KBRepository:
    """Create a KBRepository with a mocked session."""
    return KBRepository(mock_session)


# ---------------------------------------------------------------------------
# find_canon_for_series
# ---------------------------------------------------------------------------


class TestFindCanonForSeries:
    """Tests for KBRepository.find_canon_for_series()."""

    async def test_returns_series_kb_entries_for_canon_rows(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """Canon rows (novel_id IS NULL) map to SeriesKBEntry instances."""
        series_id = uuid.uuid4()
        canon = [
            make_kb_model(id=uuid.uuid4(), series_id=series_id, novel_id=None, slug="alice"),
            make_kb_model(id=uuid.uuid4(), series_id=series_id, novel_id=None, slug="bob"),
        ]
        mock_session.execute.return_value = make_result(scalars=canon)

        result = await repo.find_canon_for_series(series_id)

        assert len(result) == 2
        assert all(isinstance(e, SeriesKBEntry) for e in result)
        assert {e.slug for e in result} == {"alice", "bob"}
        assert all(e.series_id == series_id for e in result)
        assert all(e.novel_id is None for e in result)

    async def test_empty_list_when_no_canon_entries(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """An empty result yields an empty list."""
        mock_session.execute.return_value = make_result(scalars=[])

        result = await repo.find_canon_for_series(uuid.uuid4())

        assert result == []

    async def test_carries_through_model_fields(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """Converter copies core fields (name, entity_type, body, tags)."""
        series_id = uuid.uuid4()
        entry_id = uuid.uuid4()
        canon = [
            make_kb_model(
                id=entry_id,
                series_id=series_id,
                novel_id=None,
                name="Aria",
                entity_type="location",
                body="A tall tower.",
                tags=["landmark"],
                slug="aria",
            )
        ]
        mock_session.execute.return_value = make_result(scalars=canon)

        result = await repo.find_canon_for_series(series_id)

        assert result[0].name == "Aria"
        assert result[0].entity_type == "location"
        assert result[0].body == "A tall tower."
        assert result[0].tags == ["landmark"]
        assert result[0].id == entry_id


# ---------------------------------------------------------------------------
# find_overlay_for_novel
# ---------------------------------------------------------------------------


class TestFindOverlayForNovel:
    """Tests for KBRepository.find_overlay_for_novel()."""

    async def test_returns_novel_kb_entries_for_overlay_rows(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """Overlay rows (novel_id set) map to NovelKBEntry instances."""
        novel_id = uuid.uuid4()
        series_id = uuid.uuid4()
        overlay = [
            make_kb_model(
                id=uuid.uuid4(),
                novel_id=novel_id,
                series_id=series_id,
                base_entry_id=uuid.uuid4(),
                slug="alice-overlay",
            ),
        ]
        mock_session.execute.return_value = make_result(scalars=overlay)

        result = await repo.find_overlay_for_novel(novel_id)

        assert len(result) == 1
        assert isinstance(result[0], NovelKBEntry)
        assert result[0].novel_id == novel_id

    async def test_empty_list_when_no_overlay_entries(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """An empty result yields an empty list."""
        mock_session.execute.return_value = make_result(scalars=[])

        result = await repo.find_overlay_for_novel(uuid.uuid4())

        assert result == []


# ---------------------------------------------------------------------------
# find_merged_for_novel
# ---------------------------------------------------------------------------


class TestFindMergedForNovel:
    """Tests for KBRepository.find_merged_for_novel()."""

    async def test_overlay_wins_on_slug_collision(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """When canon and overlay share a slug, the overlay entry wins."""
        series_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        canon_only = make_kb_model(
            id=uuid.uuid4(), series_id=series_id, novel_id=None, slug="bob", name="Canon Bob"
        )
        canon_alice = make_kb_model(
            id=uuid.uuid4(), series_id=series_id, novel_id=None, slug="alice", name="Canon Alice"
        )
        overlay_alice = make_kb_model(
            id=uuid.uuid4(),
            novel_id=novel_id,
            series_id=series_id,
            slug="alice",
            name="Overlay Alice",
        )

        # Execute is called 3x: novel.series_id, canon, overlay.
        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=series_id),
            make_result(scalars=[canon_only, canon_alice]),
            make_result(scalars=[overlay_alice]),
        ]

        merged = await repo.find_merged_for_novel(novel_id)

        by_slug = {e.slug: e for e in merged}
        # Two distinct slugs survive: "bob" (canon only) + "alice" (overlay won).
        assert set(by_slug) == {"bob", "alice"}
        assert isinstance(by_slug["alice"], NovelKBEntry)
        assert by_slug["alice"].name == "Overlay Alice"
        assert isinstance(by_slug["bob"], SeriesKBEntry)
        assert by_slug["bob"].name == "Canon Bob"

    async def test_returns_overlay_only_when_novel_has_no_series(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """A standalone novel (series_id NULL) merges to just its overlays."""
        novel_id = uuid.uuid4()
        overlay = make_kb_model(id=uuid.uuid4(), novel_id=novel_id, slug="solo")
        # Execute called 2x: novel.series_id (None) → early return, then overlay.
        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=None),
            make_result(scalars=[overlay]),
        ]

        merged = await repo.find_merged_for_novel(novel_id)

        assert len(merged) == 1
        assert isinstance(merged[0], NovelKBEntry)
        assert merged[0].slug == "solo"

    async def test_empty_when_no_entries_at_all(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """No canon and no overlay yields an empty merged list."""
        series_id = uuid.uuid4()
        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=series_id),
            make_result(scalars=[]),
            make_result(scalars=[]),
        ]

        merged = await repo.find_merged_for_novel(uuid.uuid4())

        assert merged == []

    async def test_canon_only_when_no_overlay(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """Canon entries pass through unchanged when no overlay exists."""
        series_id = uuid.uuid4()
        canon = make_kb_model(
            id=uuid.uuid4(), series_id=series_id, novel_id=None, slug="only-canon"
        )
        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=series_id),
            make_result(scalars=[canon]),
            make_result(scalars=[]),
        ]

        merged = await repo.find_merged_for_novel(uuid.uuid4())

        assert len(merged) == 1
        assert isinstance(merged[0], SeriesKBEntry)
        assert merged[0].slug == "only-canon"
