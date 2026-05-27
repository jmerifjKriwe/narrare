"""Tests for writing/_classify.py — entity classification for context assembly.

Covers:
1. classify_entities with empty inputs
2. Pinned entities separated correctly
3. Referenced entities (by ref_ids and is_referenced flag)
4. Connected entities (first-degree connections of referenced)
5. Suggested entities (remaining, sorted by relevance)
6. Edge cases: overlap between categories
"""

from __future__ import annotations

from narrare_core.writing._classify import classify_entities
from narrare_core.writing.context_models import KBEntity


def _entity(
    entity_id: str = "ent-1",
    entity_type: str = "character",
    name: str = "Test",
    similarity: float = 0.5,
    frequency: float = 0.5,
    recency: float = 0.5,
    is_pinned: bool = False,
    is_referenced: bool = False,
) -> KBEntity:
    return KBEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        content="Content.",
        similarity_score=similarity,
        frequency_score=frequency,
        recency_score=recency,
        is_pinned=is_pinned,
        is_referenced=is_referenced,
    )


class TestClassifyEntitiesEmpty:
    """classify_entities handles empty inputs."""

    def test_no_entities(self) -> None:
        pinned, referenced, connected, suggested = classify_entities([], set(), {})
        assert pinned == []
        assert referenced == []
        assert connected == []
        assert suggested == []


class TestClassifyEntitiesPinned:
    """Pinned entities are separated first."""

    def test_pinned_entities(self) -> None:
        entities = [
            _entity("e1", is_pinned=True),
            _entity("e2", is_pinned=False),
        ]
        pinned, _referenced, _connected, _suggested = classify_entities(entities, set(), {})
        assert len(pinned) == 1
        assert pinned[0].entity_id == "e1"

    def test_multiple_pinned(self) -> None:
        entities = [
            _entity("e1", is_pinned=True),
            _entity("e2", is_pinned=True),
            _entity("e3", is_pinned=False),
        ]
        pinned, _referenced, _connected, _suggested = classify_entities(entities, set(), {})
        assert len(pinned) == 2


class TestClassifyEntitiesReferenced:
    """Referenced entities identified by ref_ids or is_referenced flag."""

    def test_referenced_by_ref_ids(self) -> None:
        entities = [
            _entity("e1"),
            _entity("e2"),
            _entity("e3"),
        ]
        _pinned, referenced, _connected, _suggested = classify_entities(entities, {"e1", "e3"}, {})
        ref_ids = {e.entity_id for e in referenced}
        assert "e1" in ref_ids
        assert "e3" in ref_ids
        assert "e2" not in ref_ids

    def test_referenced_by_is_referenced_flag(self) -> None:
        entities = [
            _entity("e1", is_referenced=True),
            _entity("e2", is_referenced=False),
        ]
        _pinned, referenced, _connected, _suggested = classify_entities(entities, set(), {})
        assert len(referenced) == 1
        assert referenced[0].entity_id == "e1"

    def test_pinned_not_in_referenced(self) -> None:
        """Pinned entities are excluded from referenced even if in ref_ids."""
        entities = [
            _entity("e1", is_pinned=True),
            _entity("e2"),
        ]
        pinned, referenced, _connected, _suggested = classify_entities(entities, {"e1", "e2"}, {})
        assert len(pinned) == 1
        assert pinned[0].entity_id == "e1"
        assert len(referenced) == 1
        assert referenced[0].entity_id == "e2"


class TestClassifyEntitiesConnected:
    """Connected entities are first-degree connections of referenced."""

    def test_connected_entities(self) -> None:
        entities = [
            _entity("e1"),
            _entity("e2"),  # connected to e1
            _entity("e3"),  # not connected
        ]
        connections = {"e1": {"e2"}}
        _pinned, _referenced, connected, _suggested = classify_entities(
            entities, {"e1"}, connections
        )
        assert len(connected) == 1
        assert connected[0].entity_id == "e2"

    def test_connected_excludes_referenced_and_pinned(self) -> None:
        entities = [
            _entity("e1", is_pinned=True),
            _entity("e2"),
            _entity("e3"),  # connected to e2 but also referenced
        ]
        connections = {"e2": {"e1", "e3"}}
        _pinned, _referenced, connected, _suggested = classify_entities(
            entities, {"e2", "e3"}, connections
        )
        conn_ids = {e.entity_id for e in connected}
        assert "e1" not in conn_ids  # pinned excluded
        assert "e3" not in conn_ids  # referenced excluded


class TestClassifyEntitiesSuggested:
    """Suggested entities are remaining, sorted by relevance."""

    def test_suggested_sorted_by_relevance(self) -> None:
        entities = [
            _entity("e1", is_pinned=True),
            _entity("e2", is_referenced=True),
            _entity("e3", similarity=0.2, frequency=0.1, recency=0.1),  # low relevance
            _entity("e4", similarity=0.9, frequency=0.9, recency=0.9),  # high relevance
            _entity("e5", similarity=0.5, frequency=0.5, recency=0.5),  # medium
        ]
        _pinned, _referenced, _connected, suggested = classify_entities(entities, set(), {})
        assert len(suggested) == 3
        # Sorted by relevance descending
        assert suggested[0].entity_id == "e4"
        assert suggested[1].entity_id == "e5"
        assert suggested[2].entity_id == "e3"

    def test_suggested_excludes_all_other_categories(self) -> None:
        entities = [
            _entity("e1", is_pinned=True),
            _entity("e2", is_referenced=True),
            _entity("e3"),  # suggested
        ]
        connections = {"e2": set()}
        _pinned, _referenced, _connected, suggested = classify_entities(
            entities, set(), connections
        )
        sugg_ids = {e.entity_id for e in suggested}
        assert "e1" not in sugg_ids
        assert "e2" not in sugg_ids
        assert "e3" in sugg_ids
