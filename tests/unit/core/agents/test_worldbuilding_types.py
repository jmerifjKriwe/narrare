"""Tests for agents/worldbuilding_types.py — Pydantic model validation.

Covers:
1. Phase1EntitySummary validation
2. Phase1GapOutput validation and defaults
3. Phase1ConnectionOutput validation
4. WorldbuildingPhase1Output validation
5. Phase2ConsistencyOutput validation
6. WorldbuildingPhase2Output validation
7. Edge cases: confidence bounds, score bounds
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.worldbuilding_types import (
    Phase1ConnectionOutput,
    Phase1EntitySummary,
    Phase1GapOutput,
    Phase2ConsistencyOutput,
    WorldbuildingPhase1Output,
    WorldbuildingPhase2Output,
)

# ---------------------------------------------------------------------------
# Phase1EntitySummary
# ---------------------------------------------------------------------------


class TestPhase1EntitySummary:
    """Phase1EntitySummary requires all fields."""

    def test_full_creation(self) -> None:
        summary = Phase1EntitySummary(
            entry_id="ent-1",
            name="Alice",
            entity_type="character",
            field_fill_rate=0.7,
            relationship_count=3,
            has_body=True,
            chapter_references=5,
        )
        assert summary.entry_id == "ent-1"
        assert summary.field_fill_rate == 0.7
        assert summary.chapter_references == 5

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            Phase1EntitySummary(entry_id="ent-1", name="Alice")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Phase1GapOutput
# ---------------------------------------------------------------------------


class TestPhase1GapOutput:
    """Phase1GapOutput has sensible defaults."""

    def test_minimal(self) -> None:
        gap = Phase1GapOutput(
            gap_type="missing_entity",
            description="No villain defined",
        )
        assert gap.gap_type == "missing_entity"
        assert gap.description == "No villain defined"
        assert gap.entity_id is None
        assert gap.severity == "major"
        assert gap.story_relevance == 0.5

    def test_full(self) -> None:
        gap = Phase1GapOutput(
            entity_id="ent-1",
            entity_name="Castle",
            entity_type="location",
            gap_type="missing_field",
            field_key="history",
            description="No history defined",
            related_entity_type="character",
            story_relevance=0.8,
            severity="critical",
        )
        assert gap.field_key == "history"
        assert gap.severity == "critical"

    def test_story_relevance_bounds_reject_negative(self) -> None:
        with pytest.raises(ValidationError):
            Phase1GapOutput(gap_type="test", description="test", story_relevance=-0.1)

    def test_story_relevance_bounds_reject_over_one(self) -> None:
        with pytest.raises(ValidationError):
            Phase1GapOutput(gap_type="test", description="test", story_relevance=1.5)


# ---------------------------------------------------------------------------
# Phase1ConnectionOutput
# ---------------------------------------------------------------------------


class TestPhase1ConnectionOutput:
    """Phase1ConnectionOutput requires core fields."""

    def test_full_creation(self) -> None:
        conn = Phase1ConnectionOutput(
            source_entity_id="ent-1",
            source_entity_name="Alice",
            target_entity_id="ent-2",
            target_entity_name="Bob",
            suggested_rel_type="ally",
            reasoning="They fight together.",
            confidence=0.9,
        )
        assert conn.suggested_rel_type == "ally"
        assert conn.confidence == 0.9
        assert conn.inverse_rel_type is None

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Phase1ConnectionOutput(
                source_entity_id="a",
                source_entity_name="A",
                target_entity_id="b",
                target_entity_name="B",
                suggested_rel_type="enemy",
                reasoning="They fight.",
                confidence=2.0,
            )

    def test_with_inverse_rel_type(self) -> None:
        conn = Phase1ConnectionOutput(
            source_entity_id="a",
            source_entity_name="A",
            target_entity_id="b",
            target_entity_name="B",
            suggested_rel_type="parent_of",
            inverse_rel_type="child_of",
            reasoning="Family.",
            confidence=0.7,
        )
        assert conn.inverse_rel_type == "child_of"


# ---------------------------------------------------------------------------
# WorldbuildingPhase1Output
# ---------------------------------------------------------------------------


class TestWorldbuildingPhase1Output:
    """WorldbuildingPhase1Output aggregates Phase 1 results."""

    def test_with_data(self) -> None:
        output = WorldbuildingPhase1Output(
            gaps=[Phase1GapOutput(gap_type="missing_body", description="No body")],
            connection_suggestions=[],
            assessment="Needs work.",
            worldbuilding_score=0.3,
            candidate_pairs_for_consistency=[("a", "b")],
        )
        assert len(output.gaps) == 1
        assert output.worldbuilding_score == 0.3

    def test_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            WorldbuildingPhase1Output(
                gaps=[],
                connection_suggestions=[],
                assessment="",
                worldbuilding_score=2.0,
                candidate_pairs_for_consistency=[],
            )

    def test_serialization(self) -> None:
        output = WorldbuildingPhase1Output(
            gaps=[],
            connection_suggestions=[],
            assessment="Good world.",
            worldbuilding_score=0.85,
            candidate_pairs_for_consistency=[],
        )
        data = output.model_dump()
        assert data["assessment"] == "Good world."
        assert data["worldbuilding_score"] == 0.85


# ---------------------------------------------------------------------------
# Phase2ConsistencyOutput
# ---------------------------------------------------------------------------


class TestPhase2ConsistencyOutput:
    """Phase2ConsistencyOutput captures a single consistency issue."""

    def test_full_creation(self) -> None:
        issue = Phase2ConsistencyOutput(
            category="timeline",
            entity_ids=["ent-1", "ent-2"],
            entity_names=["Event A", "Event B"],
            description="Timeline contradiction.",
            contradiction="Event A happens before and after Event B.",
            severity="major",
            confidence=0.75,
        )
        assert issue.category == "timeline"
        assert len(issue.entity_ids) == 2
        assert issue.suggested_resolution is None

    def test_with_resolution(self) -> None:
        issue = Phase2ConsistencyOutput(
            category="geography",
            entity_ids=["ent-1"],
            entity_names=["Mountain"],
            description="Height changes.",
            contradiction="Mountain height varies.",
            suggested_resolution="Fix to 3000m in all references.",
            confidence=0.6,
        )
        assert issue.suggested_resolution == "Fix to 3000m in all references."


# ---------------------------------------------------------------------------
# WorldbuildingPhase2Output
# ---------------------------------------------------------------------------


class TestWorldbuildingPhase2Output:
    """WorldbuildingPhase2Output aggregates Phase 2 results."""

    def test_empty(self) -> None:
        output = WorldbuildingPhase2Output(issues=[], assessment="Clean.")
        assert output.issues == []
        assert output.assessment == "Clean."

    def test_with_issues(self) -> None:
        output = WorldbuildingPhase2Output(
            issues=[
                Phase2ConsistencyOutput(
                    category="politics",
                    entity_ids=["e1"],
                    entity_names=["Faction A"],
                    description="Power imbalance.",
                    contradiction="Faction has no territory.",
                    confidence=0.5,
                ),
            ],
            assessment="Some issues found.",
        )
        assert len(output.issues) == 1

    def test_serialization_roundtrip(self) -> None:
        output = WorldbuildingPhase2Output(
            issues=[],
            assessment="All clear.",
        )
        data = output.model_dump()
        restored = WorldbuildingPhase2Output.model_validate(data)
        assert restored.assessment == output.assessment
