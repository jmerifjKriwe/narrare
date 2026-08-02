"""Unit tests for KBRepository promote/demote scope mutations.

Series Foundation Spec 1, Task 2.2 — KB scope mutations (write path).

Covers ``promote_to_canon`` (Novel-Overlay → Series-Canon) and
``demote_to_overlay`` (Series-Canon → Novel-Overlay). Query/merge tests live
in ``test_scope_repository.py`` (RULE-04 file-size split).

The repositories raise domain ``ConflictError`` directly on a scope-invariant
violation (T9 — formerly ``ValueError``), and ``demote_to_overlay`` enforces the
Canon-integrity guard (D4) + clears ``series_id`` (D6). Uses a mock
``AsyncSession`` (ADR-030 fakes pattern); the methods mutate real ``KBEntry``
instances and convert them to Core Pydantic types.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.kb.repository import KBRepository
from narrare_core.kb.schemas.entry import NovelKBEntry, SeriesKBEntry
from narrare_core.shared.errors import ConflictError
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

    async def test_raises_conflict_when_entry_not_found(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """A missing entry raises ConflictError (scope invariant → 409)."""
        mock_session.execute.return_value = make_result(scalar_one_or_none=None)

        with pytest.raises(ConflictError, match="not an overlay"):
            await repo.promote_to_canon(uuid.uuid4(), uuid.uuid4())

    async def test_raises_conflict_when_entry_not_overlay_of_novel(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """An overlay belonging to a different novel raises ConflictError."""
        other_novel_id = uuid.uuid4()
        entry = make_kb_model(id=uuid.uuid4(), novel_id=other_novel_id, slug="alice")
        mock_session.execute.return_value = make_result(scalar_one_or_none=entry)

        with pytest.raises(ConflictError, match="not an overlay"):
            await repo.promote_to_canon(uuid.uuid4(), entry.id)

    async def test_raises_conflict_when_novel_not_in_series(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """Promoting an overlay of a standalone novel raises ConflictError."""
        novel_id = uuid.uuid4()
        entry = make_kb_model(id=uuid.uuid4(), novel_id=novel_id, slug="alice")
        novel = make_novel(id=novel_id, series_id=None)

        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=entry),
            make_result(scalar_one_or_none=novel),
        ]

        with pytest.raises(ConflictError, match="not in a series"):
            await repo.promote_to_canon(novel_id, entry.id)

    async def test_raises_conflict_when_novel_does_not_exist(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """Promoting when the novel itself is missing raises ConflictError."""
        novel_id = uuid.uuid4()
        entry = make_kb_model(id=uuid.uuid4(), novel_id=novel_id, slug="alice")
        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=entry),
            make_result(scalar_one_or_none=None),
        ]

        with pytest.raises(ConflictError, match="not in a series"):
            await repo.promote_to_canon(novel_id, entry.id)


# ---------------------------------------------------------------------------
# demote_to_overlay
# ---------------------------------------------------------------------------


class TestDemoteToOverlay:
    """Tests for KBRepository.demote_to_overlay()."""

    async def test_demotes_canon_to_overlay_clearing_series_id(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """A valid canon entry becomes a Novel-Overlay; series_id is cleared (D6)."""
        series_id = uuid.uuid4()
        target_novel_id = uuid.uuid4()
        entry = make_kb_model(
            id=uuid.uuid4(),
            series_id=series_id,
            novel_id=None,
            base_entry_id=None,
            slug="shared-lore",
        )
        # Execute called 2x: entry lookup, reliance-count (D4 guard) → 0.
        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=entry),
            make_result(scalar_one=0),
        ]

        result = await repo.demote_to_overlay(series_id, entry.id, target_novel_id)

        assert isinstance(result, NovelKBEntry)
        assert entry.novel_id == target_novel_id
        assert entry.series_id is None  # D6: overlays never persist series_id
        assert entry.base_entry_id is None
        mock_session.flush.assert_awaited()

    async def test_raises_conflict_when_entry_not_found(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """A missing entry raises ConflictError (scope invariant → 409)."""
        mock_session.execute.return_value = make_result(scalar_one_or_none=None)

        with pytest.raises(ConflictError, match="not a Canon entry"):
            await repo.demote_to_overlay(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    async def test_raises_conflict_when_entry_series_mismatch(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """An entry belonging to a different series raises ConflictError."""
        entry = make_kb_model(id=uuid.uuid4(), series_id=uuid.uuid4(), novel_id=None, slug="lore")
        mock_session.execute.return_value = make_result(scalar_one_or_none=entry)

        with pytest.raises(ConflictError, match="not a Canon entry"):
            await repo.demote_to_overlay(uuid.uuid4(), entry.id, uuid.uuid4())

    async def test_raises_conflict_when_entry_is_overlay_not_canon(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """An entry that is already an overlay (novel_id set) raises ConflictError."""
        series_id = uuid.uuid4()
        entry = make_kb_model(
            id=uuid.uuid4(), series_id=series_id, novel_id=uuid.uuid4(), slug="lore"
        )
        mock_session.execute.return_value = make_result(scalar_one_or_none=entry)

        with pytest.raises(ConflictError, match="not a Canon entry"):
            await repo.demote_to_overlay(series_id, entry.id, uuid.uuid4())

    async def test_raises_conflict_when_another_novel_relies_on_canon(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """D4 guard: if another member novel relies on the Canon entry → 409."""
        series_id = uuid.uuid4()
        target_novel_id = uuid.uuid4()
        entry = make_kb_model(
            id=uuid.uuid4(), series_id=series_id, novel_id=None, slug="shared-lore"
        )
        # reliance-count → 1 (another novel relies on it): guard trips before flush.
        mock_session.execute.side_effect = [
            make_result(scalar_one_or_none=entry),
            make_result(scalar_one=1),
        ]

        with pytest.raises(ConflictError, match="rely on it"):
            await repo.demote_to_overlay(series_id, entry.id, target_novel_id)

        mock_session.flush.assert_not_awaited()
