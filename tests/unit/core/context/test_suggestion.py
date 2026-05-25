"""Tests for context/suggestion.py — Suggestion and EntityMetadata dataclasses."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import uuid4

import pytest

from narrare_core.context.suggestion import EntityMetadata, Suggestion

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# EntityMetadata tests
# ---------------------------------------------------------------------------


class TestEntityMetadata:
    """EntityMetadata dataclass construction and immutability."""

    def test_construction_with_all_fields(self) -> None:
        last_ref = datetime(2026, 5, 20, 10, 30, 0)
        meta = EntityMetadata(
            name="Aria",
            entity_type="character",
            usage_count=5,
            last_referenced_at=last_ref,
        )
        assert meta.name == "Aria"
        assert meta.entity_type == "character"
        assert meta.usage_count == 5
        assert meta.last_referenced_at == last_ref

    def test_construction_without_last_referenced(self) -> None:
        meta = EntityMetadata(
            name="Castle",
            entity_type="location",
            usage_count=0,
            last_referenced_at=None,
        )
        assert meta.last_referenced_at is None

    def test_frozen_immutability(self) -> None:
        meta = EntityMetadata(
            name="Aria",
            entity_type="character",
            usage_count=3,
            last_referenced_at=None,
        )
        with pytest.raises(FrozenInstanceError):
            meta.name = "Changed"  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        ts = datetime(2026, 1, 1, 0, 0, 0)
        a = EntityMetadata(
            name="Aria", entity_type="character", usage_count=3, last_referenced_at=ts
        )
        b = EntityMetadata(
            name="Aria", entity_type="character", usage_count=3, last_referenced_at=ts
        )
        assert a == b

    def test_inequality_by_name(self) -> None:
        a = EntityMetadata(
            name="Aria", entity_type="character", usage_count=0, last_referenced_at=None
        )
        b = EntityMetadata(
            name="Bran", entity_type="character", usage_count=0, last_referenced_at=None
        )
        assert a != b

    def test_slots_instance(self) -> None:
        meta = EntityMetadata(
            name="Aria", entity_type="character", usage_count=0, last_referenced_at=None
        )
        assert hasattr(meta, "__slots__")


# ---------------------------------------------------------------------------
# Suggestion tests
# ---------------------------------------------------------------------------


class TestSuggestion:
    """Suggestion dataclass construction and immutability."""

    def test_construction_with_all_fields(self) -> None:
        entry_id = uuid4()
        last_ref = datetime(2026, 5, 15, 8, 0, 0)
        suggestion = Suggestion(
            entry_id=entry_id,
            entry_type="character",
            name="Aria",
            relevance_score=0.85,
            reason="mentioned_in_text",
            similarity=0.92,
            usage_count=3,
            last_referenced_at=last_ref,
        )
        assert suggestion.entry_id == entry_id
        assert suggestion.entry_type == "character"
        assert suggestion.name == "Aria"
        assert suggestion.relevance_score == 0.85
        assert suggestion.reason == "mentioned_in_text"
        assert suggestion.similarity == 0.92
        assert suggestion.usage_count == 3
        assert suggestion.last_referenced_at == last_ref

    def test_reason_semantically_similar(self) -> None:
        suggestion = Suggestion(
            entry_id=uuid4(),
            entry_type="location",
            name="Castle",
            relevance_score=0.6,
            reason="semantically_similar",
            similarity=0.7,
            usage_count=0,
            last_referenced_at=None,
        )
        assert suggestion.reason == "semantically_similar"

    def test_reason_recently_used(self) -> None:
        suggestion = Suggestion(
            entry_id=uuid4(),
            entry_type="faction",
            name="Guild",
            relevance_score=0.5,
            reason="recently_used",
            similarity=0.3,
            usage_count=10,
            last_referenced_at=datetime(2026, 5, 20),
        )
        assert suggestion.reason == "recently_used"

    def test_frozen_immutability(self) -> None:
        suggestion = Suggestion(
            entry_id=uuid4(),
            entry_type="character",
            name="Aria",
            relevance_score=0.9,
            reason="mentioned_in_text",
            similarity=0.95,
            usage_count=0,
            last_referenced_at=None,
        )
        with pytest.raises(FrozenInstanceError):
            suggestion.relevance_score = 0.5  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        eid = uuid4()
        ts = datetime(2026, 1, 1, 0, 0, 0)
        a = Suggestion(
            entry_id=eid,
            entry_type="character",
            name="A",
            relevance_score=0.9,
            reason="mentioned_in_text",
            similarity=0.95,
            usage_count=1,
            last_referenced_at=ts,
        )
        b = Suggestion(
            entry_id=eid,
            entry_type="character",
            name="A",
            relevance_score=0.9,
            reason="mentioned_in_text",
            similarity=0.95,
            usage_count=1,
            last_referenced_at=ts,
        )
        assert a == b

    def test_inequality_by_score(self) -> None:
        eid = uuid4()
        a = Suggestion(
            entry_id=eid,
            entry_type="character",
            name="A",
            relevance_score=0.9,
            reason="semantically_similar",
            similarity=0.95,
            usage_count=0,
            last_referenced_at=None,
        )
        b = Suggestion(
            entry_id=eid,
            entry_type="character",
            name="A",
            relevance_score=0.5,
            reason="semantically_similar",
            similarity=0.95,
            usage_count=0,
            last_referenced_at=None,
        )
        assert a != b

    def test_slots_instance(self) -> None:
        suggestion = Suggestion(
            entry_id=uuid4(),
            entry_type="character",
            name="X",
            relevance_score=0.5,
            reason="semantically_similar",
            similarity=0.5,
            usage_count=0,
            last_referenced_at=None,
        )
        assert hasattr(suggestion, "__slots__")
