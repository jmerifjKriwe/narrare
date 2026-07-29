"""Unit tests for KBRepository promote/demote scope mutations.

Series Foundation Spec 1, Task 2.2 — KB scope mutations (write path).

Covers ``promote_to_canon`` (Novel-Overlay → Series-Canon) and
``demote_to_overlay`` (Series-Canon → Novel-Overlay). Query/merge tests live
in ``test_scope_repository.py`` (RULE-04 file-size split).

Uses a mock ``AsyncSession`` (ADR-030 fakes pattern); the methods mutate real
``KBEntry`` instances and convert them to Core Pydantic types.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.kb.repository import KBRepository
from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry
from tests.unit.api.kb._scope_repo_helpers import make_kb_model, make_novel, make_result


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
# promote_to_canon
# ---------------------------------------------------------------------------


class TestPromoteToCanon:
    """Tests for KBRepository.promote_to_canon()."""

    async def test_promotes_overlay_to_canon(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """A valid overlay becomes Series-Canon and a SeriesKBEntry is returned."""
        novel_id = uuid.uuid4()
        series_id = uuid.uuid4()
        base_id = uuid.uuid4()
        entry = make_kb_model(
            id=uuid.uuid4(),
            novel_id=novel_id,
            series_id=None,
            base_entry_id=base_id,
            slug="alice",
        )
        novel = make_novel(id=novel_id, series_id=series_id)

        # Execute called 2x: entry lookup, novel lookup.
        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=entry),
            make_result(scalar_one_or_none=novel),
        ]

        result = await repo.promote_to_canon(novel_id, entry.id)

        assert isinstance(result, SeriesKBEntry)
        assert entry.novel_id is None
        assert entry.series_id == series_id
        assert entry.base_entry_id is None
        mock_session.flush.assert_awaited()

    async def test_raises_when_entry_not_found(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """A missing entry raises ValueError."""
        mock_session.execute.return_value = make_result(scalar_one_or_none=None)

        with pytest.raises(ValueError, match="not found"):
            await repo.promote_to_canon(uuid.uuid4(), uuid.uuid4())

    async def test_raises_when_entry_not_overlay_of_novel(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """An overlay belonging to a different novel raises ValueError."""
        other_novel_id = uuid.uuid4()
        entry = make_kb_model(id=uuid.uuid4(), novel_id=other_novel_id, slug="alice")
        mock_session.execute.return_value = make_result(scalar_one_or_none=entry)

        with pytest.raises(ValueError, match="not overlay"):
            await repo.promote_to_canon(uuid.uuid4(), entry.id)

    async def test_raises_when_novel_not_in_series(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """Promoting an overlay of a standalone novel raises ValueError."""
        novel_id = uuid.uuid4()
        entry = make_kb_model(id=uuid.uuid4(), novel_id=novel_id, slug="alice")
        novel = make_novel(id=novel_id, series_id=None)

        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=entry),
            make_result(scalar_one_or_none=novel),
        ]

        with pytest.raises(ValueError, match="not in a series"):
            await repo.promote_to_canon(novel_id, entry.id)

    async def test_raises_when_novel_does_not_exist(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """Promoting when the novel itself is missing raises ValueError."""
        novel_id = uuid.uuid4()
        entry = make_kb_model(id=uuid.uuid4(), novel_id=novel_id, slug="alice")
        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=entry),
            make_result(scalar_one_or_none=None),
        ]

        with pytest.raises(ValueError, match="not in a series"):
            await repo.promote_to_canon(novel_id, entry.id)


# ---------------------------------------------------------------------------
# demote_to_overlay
# ---------------------------------------------------------------------------


class TestDemoteToOverlay:
    """Tests for KBRepository.demote_to_overlay()."""

    async def test_demotes_canon_to_overlay(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """A valid canon entry becomes a Novel-Overlay for the target novel."""
        series_id = uuid.uuid4()
        target_novel_id = uuid.uuid4()
        entry = make_kb_model(
            id=uuid.uuid4(),
            series_id=series_id,
            novel_id=None,
            base_entry_id=None,
            slug="shared-lore",
        )
        mock_session.execute.return_value = make_result(scalar_one_or_none=entry)

        result = await repo.demote_to_overlay(series_id, entry.id, target_novel_id)

        assert isinstance(result, NovelKBEntry)
        assert entry.novel_id == target_novel_id
        assert entry.base_entry_id is None
        mock_session.flush.assert_awaited()

    async def test_raises_when_entry_not_found(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """A missing entry raises ValueError."""
        mock_session.execute.return_value = make_result(scalar_one_or_none=None)

        with pytest.raises(ValueError, match="not found"):
            await repo.demote_to_overlay(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    async def test_raises_when_entry_series_mismatch(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """An entry belonging to a different series raises ValueError."""
        entry = make_kb_model(id=uuid.uuid4(), series_id=uuid.uuid4(), novel_id=None, slug="lore")
        mock_session.execute.return_value = make_result(scalar_one_or_none=entry)

        with pytest.raises(ValueError, match="not canon"):
            await repo.demote_to_overlay(uuid.uuid4(), entry.id, uuid.uuid4())

    async def test_raises_when_entry_is_overlay_not_canon(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """An entry that is already an overlay (novel_id set) raises ValueError."""
        series_id = uuid.uuid4()
        entry = make_kb_model(
            id=uuid.uuid4(), series_id=series_id, novel_id=uuid.uuid4(), slug="lore"
        )
        mock_session.execute.return_value = make_result(scalar_one_or_none=entry)

        with pytest.raises(ValueError, match="not canon"):
            await repo.demote_to_overlay(series_id, entry.id, uuid.uuid4())
