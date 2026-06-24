"""Tests for KBSuggestedEntity and KBSuggestionResult models (ADR-048 Q3).

Covers: field validation, frozen immutability, default values, and
constraint enforcement (relevance_score 0-1, token_count >= 0).

See: ADR-048 Q3, CONSTRAINTS.md RULE-03/RULE-10.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.ai_invocation.enrichers.kb_suggested import (
    KBSuggestedEntity,
    KBSuggestionResult,
)


def _valid_entity(**overrides: object) -> KBSuggestedEntity:
    """Create a valid KBSuggestedEntity with sensible defaults."""
    defaults: dict[str, object] = {
        "entity_id": "char-001",
        "name": "John Doe",
        "entity_type": "character",
        "summary": "A mysterious wanderer.",
        "relevance_score": 0.85,
        "token_count": 120,
        "provenance": "kb_repository",
    }
    defaults.update(overrides)
    return KBSuggestedEntity(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# KBSuggestedEntity
# ---------------------------------------------------------------------------


class TestKBSuggestedEntityValidation:
    """KBSuggestedEntity field validation and constraints."""

    def test_valid_entity_creates_successfully(self) -> None:
        entity = _valid_entity()
        assert entity.entity_id == "char-001"
        assert entity.name == "John Doe"
        assert entity.entity_type == "character"
        assert entity.summary == "A mysterious wanderer."
        assert entity.relevance_score == 0.85
        assert entity.token_count == 120
        assert entity.provenance == "kb_repository"

    def test_relevance_score_zero_is_valid(self) -> None:
        entity = _valid_entity(relevance_score=0.0)
        assert entity.relevance_score == 0.0

    def test_relevance_score_one_is_valid(self) -> None:
        entity = _valid_entity(relevance_score=1.0)
        assert entity.relevance_score == 1.0

    def test_relevance_score_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _valid_entity(relevance_score=1.5)

    def test_relevance_score_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _valid_entity(relevance_score=-0.1)

    def test_token_count_zero_is_valid(self) -> None:
        entity = _valid_entity(token_count=0)
        assert entity.token_count == 0

    def test_token_count_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _valid_entity(token_count=-1)

    def test_missing_required_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            KBSuggestedEntity(  # type: ignore[call-arg]
                name="John",
                entity_type="character",
                summary="...",
                relevance_score=0.5,
                token_count=10,
                provenance="kb",
            )

    def test_frozen_model_rejects_mutation(self) -> None:
        entity = _valid_entity()
        with pytest.raises(ValidationError):
            entity.name = "Changed"  # type: ignore[misc]

    def test_frozen_model_rejects_del(self) -> None:
        entity = _valid_entity()
        with pytest.raises(ValidationError):
            del entity.entity_id  # type: ignore[misc]


# ---------------------------------------------------------------------------
# KBSuggestionResult
# ---------------------------------------------------------------------------


class TestKBSuggestionResultValidation:
    """KBSuggestionResult field validation and defaults."""

    def test_empty_result_with_defaults(self) -> None:
        result = KBSuggestionResult(source="kb_repository", total_token_count=0)
        assert result.entities == ()
        assert result.total_token_count == 0
        assert result.source == "kb_repository"
        assert result.query_metadata == {}

    def test_result_with_entities(self) -> None:
        e1 = _valid_entity(entity_id="1", token_count=100)
        e2 = _valid_entity(entity_id="2", token_count=200)
        result = KBSuggestionResult(
            entities=(e1, e2),
            total_token_count=300,
            source="kb_repository",
        )
        assert len(result.entities) == 2
        assert result.entities[0].entity_id == "1"
        assert result.entities[1].entity_id == "2"
        assert result.total_token_count == 300

    def test_total_token_count_zero_is_valid(self) -> None:
        result = KBSuggestionResult(source="kb", total_token_count=0)
        assert result.total_token_count == 0

    def test_total_token_count_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            KBSuggestionResult(source="kb", total_token_count=-1)

    def test_query_metadata_defaults_to_empty_dict(self) -> None:
        result = KBSuggestionResult(source="kb", total_token_count=0)
        assert result.query_metadata == {}

    def test_query_metadata_populated(self) -> None:
        result = KBSuggestionResult(
            source="kb",
            total_token_count=0,
            query_metadata={"total_entries_found": "42", "query_intent": "extend"},
        )
        assert result.query_metadata["total_entries_found"] == "42"
        assert result.query_metadata["query_intent"] == "extend"

    def test_frozen_result_rejects_mutation(self) -> None:
        result = KBSuggestionResult(source="kb", total_token_count=0)
        with pytest.raises(ValidationError):
            result.source = "other"  # type: ignore[misc]

    def test_frozen_result_entities_immutable(self) -> None:
        e1 = _valid_entity()
        result = KBSuggestionResult(
            entities=(e1,),
            total_token_count=100,
            source="kb",
        )
        with pytest.raises(ValidationError):
            result.entities = ()  # type: ignore[misc]

    def test_source_is_required(self) -> None:
        with pytest.raises(ValidationError):
            KBSuggestionResult(total_token_count=0)  # type: ignore[call-arg]
