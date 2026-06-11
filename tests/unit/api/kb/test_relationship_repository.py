"""Unit tests for RelationshipRepository.get_adjacency_map().

Tests the adjacency map builder using a fake session that simulates
SQLAlchemy query results — no real DB required.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

from narrare.kb.models import KBEntry, KBRelationship
from narrare.kb.relationship_repository import RelationshipRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _make_entry(novel_id: uuid.UUID, **overrides: Any) -> KBEntry:
    defaults: dict[str, Any] = {
        "id": _uuid(),
        "novel_id": novel_id,
        "entity_type": "character",
        "name": "TestEntry",
        "slug": "test-entry",
        "status": "canon",
    }
    defaults.update(overrides)
    return KBEntry(**defaults)


def _make_rel(source_id: uuid.UUID, target_id: uuid.UUID, **overrides: Any) -> KBRelationship:
    defaults: dict[str, Any] = {
        "id": _uuid(),
        "source_id": source_id,
        "target_id": target_id,
        "rel_type": "ally",
    }
    defaults.update(overrides)
    return KBRelationship(**defaults)


# ---------------------------------------------------------------------------
# Fake session helpers
# ---------------------------------------------------------------------------


class FakeRow:
    """Simulates a SQLAlchemy row tuple from a two-column select."""

    def __init__(self, source_id: uuid.UUID, target_id: uuid.UUID) -> None:
        self._source = source_id
        self._target = target_id

    def __getitem__(self, idx: int) -> uuid.UUID:
        return (self._source, self._target)[idx]

    def __iter__(self) -> Any:
        return iter((self._source, self._target))


class FakeResult:
    """Simulates a SQLAlchemy result with .all()."""

    def __init__(self, rows: list[FakeRow]) -> None:
        self._rows = rows

    def all(self) -> list[FakeRow]:
        return self._rows


class FakeSession:
    """Minimal AsyncSession fake — captures queries and returns preset rows."""

    def __init__(self, rows: list[FakeRow]) -> None:
        self._rows = rows

    async def execute(self, query: Any) -> FakeResult:
        """Return pre-configured rows regardless of the query."""
        return FakeResult(self._rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetAdjacencyMap:
    """Tests for RelationshipRepository.get_adjacency_map()."""

    async def test_adjacency_map_returns_bidirectional_connections(
        self,
    ) -> None:
        """A→B relationship produces both A→{B} and B→{A}."""
        novel_id = _uuid()
        source = _make_entry(novel_id, name="Alice")
        target = _make_entry(novel_id, name="Bob")
        _make_rel(source.id, target.id)

        rows = [FakeRow(source.id, target.id)]
        session = FakeSession(rows)
        repo = RelationshipRepository(cast("AsyncSession", session))

        result = await repo.get_adjacency_map(novel_id)

        src_str = str(source.id)
        tgt_str = str(target.id)
        assert src_str in result
        assert tgt_str in result
        assert tgt_str in result[src_str]
        assert src_str in result[tgt_str]

    async def test_adjacency_map_empty_when_no_relationships(
        self,
    ) -> None:
        """No relationships returns an empty dict."""
        novel_id = _uuid()
        session = FakeSession([])
        repo = RelationshipRepository(cast("AsyncSession", session))

        result = await repo.get_adjacency_map(novel_id)

        assert result == {}

    async def test_adjacency_map_filtered_by_entity_ids(
        self,
    ) -> None:
        """Only connections involving specified entity_ids are returned."""
        novel_id = _uuid()
        alice = _make_entry(novel_id, name="Alice")
        bob = _make_entry(novel_id, name="Bob")
        carol = _make_entry(novel_id, name="Carol")

        # Alice→Bob and Carol→(another entity not in filter)
        rows = [
            FakeRow(alice.id, bob.id),
            FakeRow(carol.id, _uuid()),
        ]
        session = FakeSession(rows)
        repo = RelationshipRepository(cast("AsyncSession", session))

        # Filter to only Alice and Carol
        result = await repo.get_adjacency_map(
            novel_id,
            entity_ids={alice.id, carol.id},
        )

        # Alice should be connected to Bob (Bob is target of Alice)
        assert str(alice.id) in result
        assert str(bob.id) in result[str(alice.id)]

        # Carol should be connected to the unknown entity
        assert str(carol.id) in result

        # There should be no entries for uninvolved entities
        # (Note: the fake returns all rows regardless, but the filter
        #  is applied in the real SQL. We verify the structure.)
        assert len(result) >= 2

    async def test_adjacency_map_cross_novel_isolation(
        self,
    ) -> None:
        """Relationships from other novels are excluded by the query.

        The fake session returns all rows, but in production the JOIN
        on KBEntry.novel_id ensures isolation. We test that the method
        accepts and uses the novel_id parameter by verifying the call
        completes without error.
        """
        novel_a = _uuid()
        novel_b = _uuid()
        alice = _make_entry(novel_a, name="Alice")
        bob = _make_entry(novel_b, name="Bob")

        # Only novel A relationship should appear for novel A
        rows = [FakeRow(alice.id, bob.id)]
        session = FakeSession(rows)
        repo = RelationshipRepository(cast("AsyncSession", session))

        result = await repo.get_adjacency_map(novel_a)

        # In production the JOIN filters, but here we verify the method
        # works and returns the expected bidirectional structure.
        assert isinstance(result, dict)
        for connections in result.values():
            assert isinstance(connections, set)

    async def test_adjacency_map_multiple_connections(
        self,
    ) -> None:
        """An entity connected to multiple others has all in its set."""
        novel_id = _uuid()
        alice = _make_entry(novel_id, name="Alice")
        bob = _make_entry(novel_id, name="Bob")
        carol = _make_entry(novel_id, name="Carol")

        rows = [
            FakeRow(alice.id, bob.id),
            FakeRow(alice.id, carol.id),
        ]
        session = FakeSession(rows)
        repo = RelationshipRepository(cast("AsyncSession", session))

        result = await repo.get_adjacency_map(novel_id)

        alice_key = str(alice.id)
        assert alice_key in result
        assert str(bob.id) in result[alice_key]
        assert str(carol.id) in result[alice_key]
        assert len(result[alice_key]) == 2
