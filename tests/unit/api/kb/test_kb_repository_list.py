"""Unit tests for KBRepository — list, search, and count operations.

Split from test_kb_repository.py per RULE-04.

Covers: list_entries (with filters + pagination), search (with filters),
and count_by_novel.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.kb.models import KBEntry
from narrare.kb.repository import KBRepository

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_RESULT_ATTRS = ["scalars", "scalar_one_or_none", "scalar_one"]


def _make_result(**kwargs: object) -> MagicMock:
    """Create a MagicMock that mimics SQLAlchemy's Result.

    The Result returned by session.execute() has synchronous methods
    (.scalars(), .scalar_one_or_none(), .scalar_one()), so we use
    MagicMock, not AsyncMock.
    """
    result: MagicMock = MagicMock(spec=_RESULT_ATTRS)
    for key, value in kwargs.items():
        setattr(result, key, value)
    return result


def _returning(value: object) -> MagicMock:
    """Callable mock returning *value* — satisfies RULE-TEST-01."""
    return MagicMock(spec=[], return_value=value)


def _make_entry(**overrides: object) -> MagicMock:
    """Create a mock KBEntry with default attribute values."""
    entry = MagicMock(spec=KBEntry)
    entry.id = overrides.get("id", uuid.uuid4())
    entry.novel_id = overrides.get("novel_id", uuid.uuid4())
    entry.name = overrides.get("name", "Test Entry")
    entry.slug = overrides.get("slug", "test-entry")
    entry.entity_type = overrides.get("entity_type", "character")
    entry.body = overrides.get("body", "Some body text")
    entry.tags = overrides.get("tags", ["tag1", "tag2"])
    entry.review_status = overrides.get("review_status", "approved")
    return entry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock AsyncSession for repository testing."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock(spec=AsyncSession.add)
    session.delete = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> KBRepository:
    """Create a KBRepository with a mocked session."""
    return KBRepository(mock_session)


# ---------------------------------------------------------------------------
# list_entries
# ---------------------------------------------------------------------------


class TestListEntries:
    """Tests for KBRepository.list_entries()."""

    async def test_list_entries_no_filters(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """list_entries() returns all entries for a novel when no filters given."""
        entry_a = _make_entry(name="Alice")
        entry_b = _make_entry(name="Bob")
        expected = [entry_a, entry_b]

        # First execute call returns count, second returns entries
        count_result = _make_result(scalar_one=_returning(2))
        list_result = _make_result(scalars=_returning(expected))
        mock_session.execute.side_effect = [count_result, list_result]

        novel_id = uuid.uuid4()
        entries, total = await repo.list_entries(novel_id)

        assert entries == expected
        assert total == 2
        assert mock_session.execute.await_count == 2

    async def test_list_entries_with_entity_type_filter(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """list_entries() filters by entity_type when provided."""
        entry = _make_entry(name="Gondor", entity_type="location")
        count_result = _make_result(scalar_one=_returning(1))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.list_entries(uuid.uuid4(), entity_type="location")

        assert entries == [entry]
        assert total == 1

    async def test_list_entries_with_tags_filter(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """list_entries() filters by tags when provided."""
        entry = _make_entry(name="Frodo", tags=["hobbit", "ring-bearer"])
        count_result = _make_result(scalar_one=_returning(1))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.list_entries(uuid.uuid4(), tags=["hobbit"])

        assert entries == [entry]
        assert total == 1

    async def test_list_entries_with_review_status_filter(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """list_entries() filters by review_status when provided."""
        entry = _make_entry(name="Sauron", review_status="pending")
        count_result = _make_result(scalar_one=_returning(1))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.list_entries(uuid.uuid4(), review_status="pending")

        assert entries == [entry]
        assert total == 1

    async def test_list_entries_with_all_filters(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """list_entries() applies all filters simultaneously."""
        entry = _make_entry(
            name="Mordor",
            entity_type="location",
            tags=["evil", "volcanic"],
            review_status="approved",
        )
        count_result = _make_result(scalar_one=_returning(1))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.list_entries(
            novel_id=uuid.uuid4(),
            entity_type="location",
            tags=["evil"],
            review_status="approved",
        )

        assert entries == [entry]
        assert total == 1

    async def test_list_entries_pagination(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """list_entries() applies pagination with offset and limit."""
        entry = _make_entry(name="Page 2 Entry")
        count_result = _make_result(scalar_one=_returning(25))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        # page=2, page_size=10 means offset=10, limit=10
        entries, total = await repo.list_entries(uuid.uuid4(), page=2, page_size=10)

        assert entries == [entry]
        assert total == 25

    async def test_list_entries_empty_result(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """list_entries() returns empty list and zero count when no entries."""
        count_result = _make_result(scalar_one=_returning(0))
        list_result = _make_result(scalars=_returning([]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.list_entries(uuid.uuid4())

        assert entries == []
        assert total == 0

    async def test_list_entries_uses_default_page_size(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """list_entries() defaults page=1 and page_size=50."""
        entries = [_make_entry(name=f"Entry-{i}") for i in range(50)]
        count_result = _make_result(scalar_one=_returning(100))
        list_result = _make_result(scalars=_returning(entries))
        mock_session.execute.side_effect = [count_result, list_result]

        result_entries, total = await repo.list_entries(uuid.uuid4())

        assert len(result_entries) == 50
        assert total == 100


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for KBRepository.search()."""

    async def test_search_returns_matching_entries(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search() finds entries matching the query in name or body."""
        entry = _make_entry(name="Wizard", body="Gandalf the Grey")
        count_result = _make_result(scalar_one=_returning(1))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.search(uuid.uuid4(), "Gandalf")

        assert entries == [entry]
        assert total == 1

    async def test_search_returns_empty_when_no_match(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search() returns empty list when nothing matches."""
        count_result = _make_result(scalar_one=_returning(0))
        list_result = _make_result(scalars=_returning([]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.search(uuid.uuid4(), "Nonexistent")

        assert entries == []
        assert total == 0

    async def test_search_filters_by_entity_type(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search() applies entity_type filter when provided."""
        entry = _make_entry(name="Rivendell", entity_type="location")
        count_result = _make_result(scalar_one=_returning(1))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.search(uuid.uuid4(), "Rivendell", entity_type="location")

        assert entries == [entry]
        assert total == 1

    async def test_search_filters_by_tags(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search() applies tags filter when provided."""
        entry = _make_entry(name="Elrond", tags=["elf", "lord"])
        count_result = _make_result(scalar_one=_returning(1))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.search(uuid.uuid4(), "Elrond", tags=["elf"])

        assert entries == [entry]
        assert total == 1

    async def test_search_with_all_filters_and_pagination(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search() applies all filters and pagination simultaneously."""
        entry = _make_entry(
            name="Minas Tirith",
            entity_type="location",
            tags=["city", "gondor"],
        )
        count_result = _make_result(scalar_one=_returning(1))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.search(
            novel_id=uuid.uuid4(),
            query="Minas",
            entity_type="location",
            tags=["gondor"],
            page=1,
            page_size=10,
        )

        assert entries == [entry]
        assert total == 1

    async def test_search_finds_by_body_content(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search() matches the query against body text."""
        entry = _make_entry(name="Misc", body="Hidden treasure here")
        count_result = _make_result(scalar_one=_returning(1))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.search(uuid.uuid4(), "treasure")

        assert entries == [entry]
        assert total == 1

    async def test_search_with_no_filters_uses_search_only(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search() works with only novel_id and query (no optional filters)."""
        entry = _make_entry(name="Aragorn", body="Son of Arathorn")
        count_result = _make_result(scalar_one=_returning(1))
        list_result = _make_result(scalars=_returning([entry]))
        mock_session.execute.side_effect = [count_result, list_result]

        entries, total = await repo.search(uuid.uuid4(), "Aragorn")

        assert entries == [entry]
        assert total == 1


# ---------------------------------------------------------------------------
# count_by_novel
# ---------------------------------------------------------------------------


class TestCountByNovel:
    """Tests for KBRepository.count_by_novel()."""

    async def test_count_by_novel_returns_correct_count(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """count_by_novel() returns the total entry count for a novel."""
        result_mock = _make_result(scalar_one=_returning(42))
        mock_session.execute.return_value = result_mock

        count = await repo.count_by_novel(uuid.uuid4())

        assert count == 42

    async def test_count_by_novel_returns_zero_when_no_entries(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """count_by_novel() returns 0 when no entries exist."""
        result_mock = _make_result(scalar_one=_returning(0))
        mock_session.execute.return_value = result_mock

        count = await repo.count_by_novel(uuid.uuid4())

        assert count == 0
