"""Tests for agents/kb_improve_types.py — Pydantic model validation.

Covers:
1. SuggestionType enum values
2. ImprovementSuggestion validation and defaults
3. KBImproveOutput validation
4. KBImproveDeps defaults and custom values
5. Edge cases: confidence bounds, optional fields
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.kb_improve_types import (
    ImprovementSuggestion,
    KBImproveDeps,
    KBImproveOutput,
    SuggestionType,
)

# ---------------------------------------------------------------------------
# SuggestionType
# ---------------------------------------------------------------------------


class TestSuggestionType:
    """SuggestionType enum has all expected values."""

    def test_add_field(self) -> None:
        assert SuggestionType.ADD_FIELD == "add_field"

    def test_connect(self) -> None:
        assert SuggestionType.CONNECT == "connect"

    def test_expand(self) -> None:
        assert SuggestionType.EXPAND == "expand"

    def test_reorganize(self) -> None:
        assert SuggestionType.REORGANIZE == "reorganize"

    def test_all_values(self) -> None:
        all_values = list(SuggestionType)
        assert len(all_values) == 4


# ---------------------------------------------------------------------------
# ImprovementSuggestion
# ---------------------------------------------------------------------------


class TestImprovementSuggestion:
    """ImprovementSuggestion validates required and optional fields."""

    def test_minimal_creation(self) -> None:
        s = ImprovementSuggestion(
            type=SuggestionType.EXPAND,
            target="backstory",
            description="Too short.",
            confidence=0.7,
        )
        assert s.type == SuggestionType.EXPAND
        assert s.proposed_content is None
        assert s.related_entity_id is None
        assert s.reasoning is None

    def test_full_creation(self) -> None:
        s = ImprovementSuggestion(
            type=SuggestionType.CONNECT,
            target="location",
            description="No home location.",
            proposed_content="The Castle",
            related_entity_id="loc-1",
            related_entity_name="Castle",
            confidence=0.85,
            reasoning="Character should be connected to their home.",
        )
        assert s.related_entity_id == "loc-1"
        assert s.related_entity_name == "Castle"
        assert s.reasoning is not None

    def test_confidence_bounds_reject_negative(self) -> None:
        with pytest.raises(ValidationError):
            ImprovementSuggestion(
                type=SuggestionType.EXPAND,
                target="test",
                description="test",
                confidence=-0.1,
            )

    def test_confidence_bounds_reject_over_one(self) -> None:
        with pytest.raises(ValidationError):
            ImprovementSuggestion(
                type=SuggestionType.EXPAND,
                target="test",
                description="test",
                confidence=1.5,
            )

    def test_confidence_boundary_zero(self) -> None:
        s = ImprovementSuggestion(
            type=SuggestionType.ADD_FIELD,
            target="test",
            description="test",
            confidence=0.0,
        )
        assert s.confidence == 0.0

    def test_confidence_boundary_one(self) -> None:
        s = ImprovementSuggestion(
            type=SuggestionType.ADD_FIELD,
            target="test",
            description="test",
            confidence=1.0,
        )
        assert s.confidence == 1.0

    def test_serialization_roundtrip(self) -> None:
        s = ImprovementSuggestion(
            type=SuggestionType.CONNECT,
            target="ally",
            description="Missing ally.",
            confidence=0.6,
            reasoning="Characters interact frequently.",
        )
        data = s.model_dump()
        restored = ImprovementSuggestion.model_validate(data)
        assert restored.type == s.type
        assert restored.target == s.target
        assert restored.reasoning == s.reasoning


# ---------------------------------------------------------------------------
# KBImproveOutput
# ---------------------------------------------------------------------------


class TestKBImproveOutput:
    """KBImproveOutput aggregates analysis results."""

    def test_with_suggestions(self) -> None:
        output = KBImproveOutput(
            suggestions=[
                ImprovementSuggestion(
                    type=SuggestionType.EXPAND,
                    target="bio",
                    description="Too short.",
                    confidence=0.7,
                ),
            ],
            overall_assessment="Needs work.",
            completeness_score=0.3,
        )
        assert len(output.suggestions) == 1
        assert output.overall_assessment == "Needs work."
        assert output.completeness_score == 0.3

    def test_default_context_used(self) -> None:
        output = KBImproveOutput(
            suggestions=[],
            overall_assessment="OK",
            completeness_score=0.9,
        )
        assert output.context_used == []

    def test_with_context_used(self) -> None:
        output = KBImproveOutput(
            suggestions=[],
            overall_assessment="OK",
            completeness_score=0.9,
            context_used=["Alice", "Castle"],
        )
        assert output.context_used == ["Alice", "Castle"]

    def test_score_bounds_reject_negative(self) -> None:
        with pytest.raises(ValidationError):
            KBImproveOutput(
                suggestions=[],
                overall_assessment="",
                completeness_score=-0.1,
            )

    def test_score_bounds_reject_over_one(self) -> None:
        with pytest.raises(ValidationError):
            KBImproveOutput(
                suggestions=[],
                overall_assessment="",
                completeness_score=1.5,
            )


# ---------------------------------------------------------------------------
# KBImproveDeps
# ---------------------------------------------------------------------------


class TestKBImproveDeps:
    """KBImproveDeps has sensible defaults."""

    def test_defaults(self) -> None:
        deps = KBImproveDeps()
        assert deps.language == "en"
        assert deps.genre == ""
        assert deps.entity_type == ""
        assert deps.template_structure is None
        assert deps.entry_content is None
        assert deps.existing_relationships is None
        assert deps.world_context is None
        assert deps.adjacency_map is None

    def test_custom_values(self) -> None:
        deps = KBImproveDeps(
            language="de",
            genre="Fantasy",
            entity_type="character",
            template_structure={"name": {"type": "string"}},
            entry_content={"name": "Alice"},
        )
        assert deps.language == "de"
        assert deps.entity_type == "character"
        assert deps.template_structure is not None
