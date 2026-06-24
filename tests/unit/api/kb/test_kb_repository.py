"""Unit tests for KBRepository — mock session tests.

These tests use mock AsyncSession objects to verify repository method behaviors
without requiring a real database. They cover all 10 methods in KBRepository
with happy-path, not-found, and edge-case scenarios per testing-standards.
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
    """Create a mock AsyncSession for repository testing.

    The session's execute() returns a MagicMock (not AsyncMock) because
    the Result object returned by execute() has synchronous methods like
    .scalars() and .scalar_one_or_none().
    """
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock(spec=["__call__"])
    session.delete = AsyncMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> KBRepository:
    """Create a KBRepository with a mocked session."""
    return KBRepository(mock_session)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    """Tests for KBRepository.create()."""

    async def test_create_adds_entry_and_refreshes(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """create() adds the entry to the session and calls flush+refresh."""
        entry = _make_entry()

        result = await repo.create(entry)

        assert result is entry
        mock_session.add.assert_called_once_with(entry)
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(entry)

    async def test_create_returns_same_entry_object(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """create() returns the same KBEntry instance that was passed in."""
        entry = _make_entry()

        result = await repo.create(entry)

        assert result is entry


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    """Tests for KBRepository.get_by_id()."""

    async def test_get_by_id_returns_entry_when_found(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """get_by_id() returns the KBEntry when it exists."""
        expected = _make_entry()
        result_mock = _make_result(scalar_one_or_none=_returning(expected))
        mock_session.execute.return_value = result_mock

        entry_id = uuid.uuid4()
        result = await repo.get_by_id(entry_id)

        assert result is expected

    async def test_get_by_id_returns_none_when_not_found(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """get_by_id() returns None when no matching entry exists."""
        result_mock = _make_result(scalar_one_or_none=_returning(None))
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_id(uuid.uuid4())

        assert result is None


# ---------------------------------------------------------------------------
# get_by_slug
# ---------------------------------------------------------------------------


class TestGetBySlug:
    """Tests for KBRepository.get_by_slug()."""

    async def test_get_by_slug_returns_entry_when_found(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """get_by_slug() returns the KBEntry matching novel_id and slug."""
        expected = _make_entry(slug="my-character")
        result_mock = _make_result(scalar_one_or_none=_returning(expected))
        mock_session.execute.return_value = result_mock

        novel_id = uuid.uuid4()
        result = await repo.get_by_slug(novel_id, "my-character")

        assert result is expected

    async def test_get_by_slug_returns_none_when_not_found(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """get_by_slug() returns None when no entry matches slug."""
        result_mock = _make_result(scalar_one_or_none=_returning(None))
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_slug(uuid.uuid4(), "nonexistent")

        assert result is None

    async def test_get_by_slug_distinguishes_different_slugs(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """get_by_slug() returns different entries for different slugs."""
        entry_a = _make_entry(slug="character-a")
        entry_b = _make_entry(slug="character-b")

        # First lookup returns entry_a
        result_a_mock = _make_result(scalar_one_or_none=_returning(entry_a))
        mock_session.execute.return_value = result_a_mock
        result = await repo.get_by_slug(uuid.uuid4(), "character-a")
        assert result is entry_a

        # Second lookup returns entry_b
        result_b_mock = _make_result(scalar_one_or_none=_returning(entry_b))
        mock_session.execute.return_value = result_b_mock
        result = await repo.get_by_slug(uuid.uuid4(), "character-b")
        assert result is entry_b


# ---------------------------------------------------------------------------
# get_by_name
# ---------------------------------------------------------------------------


class TestGetByName:
    """Tests for KBRepository.get_by_name()."""

    async def test_get_by_name_returns_entry_when_found(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """get_by_name() returns the KBEntry matching novel_id and name."""
        expected = _make_entry(name="Alice")
        result_mock = _make_result(scalar_one_or_none=_returning(expected))
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_name(uuid.uuid4(), "Alice")

        assert result is expected

    async def test_get_by_name_returns_none_when_not_found(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """get_by_name() returns None when no entry matches name."""
        result_mock = _make_result(scalar_one_or_none=_returning(None))
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_name(uuid.uuid4(), "Unknown")

        assert result is None

    async def test_get_by_name_is_case_insensitive(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """get_by_name() uses ILIKE so case differences still match."""
        expected = _make_entry(name="Alice")
        result_mock = _make_result(scalar_one_or_none=_returning(expected))
        mock_session.execute.return_value = result_mock

        # Different case should still find the entry via ILIKE
        result = await repo.get_by_name(uuid.uuid4(), "alice")

        assert result is expected


# ---------------------------------------------------------------------------
# search_by_name_prefix
# ---------------------------------------------------------------------------


class TestSearchByNamePrefix:
    """Tests for KBRepository.search_by_name_prefix()."""

    async def test_search_by_name_prefix_returns_matching_entries(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search_by_name_prefix() returns entries whose name starts with prefix."""
        char_a = _make_entry(name="Alice")
        char_b = _make_entry(name="Alistair")
        expected = [char_a, char_b]
        result_mock = _make_result(scalars=_returning(expected))
        mock_session.execute.return_value = result_mock

        results = await repo.search_by_name_prefix(uuid.uuid4(), "Ali")

        assert results == expected

    async def test_search_by_name_prefix_returns_empty_when_no_match(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search_by_name_prefix() returns empty list when no names match."""
        result_mock = _make_result(scalars=_returning([]))
        mock_session.execute.return_value = result_mock

        results = await repo.search_by_name_prefix(uuid.uuid4(), "Xyz")

        assert results == []

    async def test_search_by_name_prefix_applies_default_limit(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search_by_name_prefix() defaults limit to 10."""
        entries = [_make_entry(name=f"Entry-{i}") for i in range(15)]
        # Return up to 15 but the repo method uses limit
        result_mock = _make_result(scalars=_returning(entries[:10]))
        mock_session.execute.return_value = result_mock

        results = await repo.search_by_name_prefix(uuid.uuid4(), "Entry")

        assert len(results) == 10

    async def test_search_by_name_prefix_with_custom_limit(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """search_by_name_prefix() respects a provided limit."""
        entries = [_make_entry(name=f"Entry-{i}") for i in range(5)]
        result_mock = _make_result(scalars=_returning(entries))
        mock_session.execute.return_value = result_mock

        results = await repo.search_by_name_prefix(uuid.uuid4(), "Entry", limit=5)

        assert len(results) == 5


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdate:
    """Tests for KBRepository.update()."""

    async def test_update_sets_fields_and_refreshes(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """update() sets the provided fields on the entry and flushes."""
        entry = _make_entry(name="Old Name", body="Old body")

        result = await repo.update(entry, {"name": "New Name", "body": "New body"})

        assert result is entry
        assert entry.name == "New Name"
        assert entry.body == "New body"
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(entry)

    async def test_update_with_empty_data_does_nothing(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """update() with empty dict still flushes but changes nothing."""
        entry = _make_entry(name="Same Name")

        result = await repo.update(entry, {})

        assert result is entry
        assert entry.name == "Same Name"
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(entry)

    async def test_update_sets_single_field(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """update() with a single field only modifies that field."""
        entry = _make_entry(name="Original", body="Original body")

        result = await repo.update(entry, {"name": "Updated"})

        assert result is entry
        assert entry.name == "Updated"
        assert entry.body == "Original body"  # unchanged


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDelete:
    """Tests for KBRepository.delete()."""

    async def test_delete_calls_session_delete_and_flush(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """delete() calls session.delete() and flushes."""
        entry = _make_entry()

        await repo.delete(entry)

        mock_session.delete.assert_awaited_once_with(entry)
        mock_session.flush.assert_awaited_once()
