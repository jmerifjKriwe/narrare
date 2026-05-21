"""Tests for PostgresGraphStateStore.

Verifies serialization helpers and CRUD operations with
mocked SQLAlchemy async session.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.generation.graph_store import (
    PostgresGraphStateStore,
    _deserialize_state,
    _serialize_state,
)
from narrare.generation.models import GraphRun
from narrare_core.agents.graph_store import GraphStateStore

# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


class TestSerializeState:
    """_serialize_state — dataclass / dict / fallback."""

    def test_serialize_dataclass(self) -> None:
        """WritingState dataclass is converted to a flat dict."""
        from narrare_core.agents.writing_graph_types import WritingState, WritingStatus

        state = WritingState(
            chapter_id="ch-1",
            outline="My outline",
            status=WritingStatus.OUTLINED,
        )
        result = _serialize_state(state)
        assert result["chapter_id"] == "ch-1"
        assert result["outline"] == "My outline"
        assert result["status"] == "outlined"

    def test_serialize_dict(self) -> None:
        """Plain dict is returned as-is."""
        result = _serialize_state({"key": "val"})
        assert result == {"key": "val"}

    def test_serialize_fallback(self) -> None:
        """Non-dataclass, non-dict object is wrapped in data key."""
        result = _serialize_state(42)
        assert result == {"data": "42"}


class TestDeserializeState:
    """_deserialize_state — JSON dict back to dataclass."""

    def test_deserialize_writing_state(self) -> None:
        """Known fields are reconstructed into WritingState."""
        from narrare_core.agents.writing_graph_types import WritingState

        data = {"chapter_id": "ch-1", "outline": "Test", "unknown_field": "ignored"}
        result = _deserialize_state(data, WritingState)
        assert result is not None
        assert isinstance(result, WritingState)
        assert result.chapter_id == "ch-1"
        assert result.outline == "Test"

    def test_deserialize_empty_data_returns_none(self) -> None:
        """Empty dict returns None."""
        from narrare_core.agents.writing_graph_types import WritingState

        result = _deserialize_state({}, WritingState)
        assert result is None

    def test_deserialize_non_dataclass_type(self) -> None:
        """Non-dataclass target type returns None."""
        result = _deserialize_state({"key": "val"}, object)
        assert result is None


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """PostgresGraphStateStore implements GraphStateStore Protocol."""

    def test_is_protocol_compliant(self) -> None:
        """Structural subtyping: store satisfies the Protocol."""
        session = MagicMock(spec=AsyncSession)
        store = PostgresGraphStateStore(session)
        assert isinstance(store, GraphStateStore)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with configurable execute()."""
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock(spec=["scalar_one_or_none"])
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    session.flush = AsyncMock()
    session.add = MagicMock(spec=GraphRun)
    return session


# ---------------------------------------------------------------------------
# CRUD — mocked session
# ---------------------------------------------------------------------------


class TestPostgresGraphStateStore:
    """PostgresGraphStateStore CRUD with mocked session."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Return a fresh mock session for each test."""
        return _make_mock_session()

    @pytest.fixture
    def store(self, mock_session: AsyncMock) -> PostgresGraphStateStore:
        """PostgresGraphStateStore wired to the mock session."""
        return PostgresGraphStateStore(mock_session)

    async def test_save_creates_new_row(
        self,
        mock_session: AsyncMock,
        store: PostgresGraphStateStore,
    ) -> None:
        """Save with no existing row calls session.add."""
        await store.save("run-1", {"chapter_id": "ch-1"})

        mock_session.add.assert_called_once()

    async def test_save_updates_existing_row(
        self,
        mock_session: AsyncMock,
        store: PostgresGraphStateStore,
    ) -> None:
        """Save with existing row mutates in-place (no add)."""
        existing = GraphRun(
            run_id="run-1",
            checkpoint_data={"chapter_id": "ch-1"},
        )
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing

        await store.save("run-1", {"chapter_id": "ch-1"})

        mock_session.add.assert_not_called()
        assert existing.checkpoint_data == {"chapter_id": "ch-1"}

    async def test_save_with_chapter_id(
        self,
        mock_session: AsyncMock,
        store: PostgresGraphStateStore,
    ) -> None:
        """Optional chapter_id is set on new GraphRun."""
        await store.save(
            "run-2",
            {"outline": "test"},
            chapter_id="00000000-0000-0000-0000-000000000001",
        )

        added: GraphRun = mock_session.add.call_args[0][0]
        assert added.run_id == "run-2"
        assert str(added.chapter_id) == "00000000-0000-0000-0000-000000000001"

    async def test_load_returns_writing_state(
        self,
        mock_session: AsyncMock,
        store: PostgresGraphStateStore,
    ) -> None:
        """Load reconstructs a WritingState from persisted JSONB."""
        from narrare_core.agents.writing_graph_types import WritingState

        existing = GraphRun(
            run_id="run-1",
            checkpoint_data={
                "chapter_id": "ch-1",
                "draft": "Hello world",
                "status": "drafted",
            },
        )
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing

        result = await store.load("run-1")

        assert isinstance(result, WritingState)
        assert result.draft == "Hello world"

    async def test_load_missing_returns_none(
        self,
        mock_session: AsyncMock,
        store: PostgresGraphStateStore,
    ) -> None:
        """Load with non-existent run_id returns None."""
        result = await store.load("nonexistent")
        assert result is None

    async def test_delete_calls_delete(
        self,
        mock_session: AsyncMock,
        store: PostgresGraphStateStore,
    ) -> None:
        """Delete executes the DELETE statement."""
        await store.delete("run-1")
        assert mock_session.execute.called
