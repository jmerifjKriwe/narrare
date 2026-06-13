"""Tests for ConsistencyAgent types — validation, modes, defaults.

See consistency_types.py CONS-001 — cross-entity and cross-chapter consistency checking.

Extended for ADR-044 staged pipeline: tests for extracted_facts and timeline_envelopes.
"""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import ValidationError

from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
    ConsistencyIssue,
    ConsistencyOutput,
    ConsistencySeverity,
)
from narrare_core.agents.fact_extractor_types import (
    ExtractedFact,
    TimelineEventEnvelope,
)

# --- A. ConsistencyCheckType enum ---


class TestConsistencyCheckType:
    """Four check types: character, timeline, world, plot."""

    def test_all_four_types_exist(self) -> None:
        assert ConsistencyCheckType.CHARACTER is not None
        assert ConsistencyCheckType.TIMELINE is not None
        assert ConsistencyCheckType.WORLD is not None
        assert ConsistencyCheckType.PLOT is not None

    def test_string_values(self) -> None:
        assert ConsistencyCheckType.CHARACTER == "character"
        assert ConsistencyCheckType.TIMELINE == "timeline"
        assert ConsistencyCheckType.WORLD == "world"
        assert ConsistencyCheckType.PLOT == "plot"


# --- B. ConsistencySeverity enum ---


class TestConsistencySeverity:
    """Three severity levels: error, warning, info."""

    def test_three_severities_exist(self) -> None:
        assert ConsistencySeverity.ERROR is not None
        assert ConsistencySeverity.WARNING is not None
        assert ConsistencySeverity.INFO is not None

    def test_string_values(self) -> None:
        assert ConsistencySeverity.ERROR == "error"
        assert ConsistencySeverity.WARNING == "warning"
        assert ConsistencySeverity.INFO == "info"


# --- C. ConsistencyIssue — creation + validation ---


def _make_issue(**overrides: object) -> ConsistencyIssue:
    """Helper to build a ConsistencyIssue with sensible defaults."""
    desc = "Anna is described as blue-eyed in Ch.3 but green-eyed in Ch.1."
    facts = ["Anna has green eyes (Ch.1)", "Anna has blue eyes (Ch.3)"]
    return ConsistencyIssue(
        check_type=cast(
            "ConsistencyCheckType", overrides.get("check_type", ConsistencyCheckType.CHARACTER)
        ),
        severity=cast("ConsistencySeverity", overrides.get("severity", ConsistencySeverity.ERROR)),
        description=cast("str", overrides.get("description", desc)),
        locations=cast("list[str]", overrides.get("locations", ["Chapter 1", "Chapter 3"])),
        conflicting_facts=cast("list[str]", overrides.get("conflicting_facts", facts)),
        suggestion=cast("str | None", overrides.get("suggestion")),
        confidence=cast("float", overrides.get("confidence", 0.92)),
    )


class TestConsistencyIssue:
    """ConsistencyIssue with check_type, severity, confidence, and locations."""

    def test_basic_issue_creation(self) -> None:
        issue = _make_issue()
        assert issue.check_type == ConsistencyCheckType.CHARACTER
        assert issue.severity == ConsistencySeverity.ERROR
        assert "Anna" in issue.description
        assert len(issue.locations) == 2

    def test_confidence_validation_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            _make_issue(confidence=-0.1)

    def test_confidence_validation_rejects_over_one(self) -> None:
        with pytest.raises(ValidationError):
            _make_issue(confidence=1.5)

    def test_confidence_boundary_zero(self) -> None:
        issue = _make_issue(
            check_type=ConsistencyCheckType.PLOT,
            severity=ConsistencySeverity.INFO,
            description="Vague possible inconsistency.",
            confidence=0.0,
        )
        assert issue.confidence == 0.0

    def test_confidence_boundary_one(self) -> None:
        issue = _make_issue(
            description="Dead character speaks.",
            conflicting_facts=["Marcus died in Chapter 2", "Marcus speaks in Chapter 4"],
            confidence=1.0,
        )
        assert issue.confidence == 1.0

    def test_suggestion_is_optional(self) -> None:
        issue = _make_issue()
        assert issue.suggestion is None

    def test_suggestion_when_provided(self) -> None:
        issue = _make_issue(suggestion="Set Anna's eye color consistently to green.")
        assert issue.suggestion is not None
        assert "consistently" in issue.suggestion

    def test_locations_can_be_empty(self) -> None:
        issue = _make_issue(locations=[])
        assert issue.locations == []

    def test_conflicting_facts_required(self) -> None:
        with pytest.raises(ValidationError, match="conflicting_facts"):
            ConsistencyIssue(  # pyright: ignore[reportCallIssue]
                check_type=ConsistencyCheckType.CHARACTER,
                severity=ConsistencySeverity.ERROR,
                description="Contradiction found.",
                locations=["Chapter 1"],
                confidence=0.8,
            )


# --- D. ConsistencyDeps — defaults ---


class TestConsistencyDeps:
    """ConsistencyDeps plain class with sensible defaults."""

    def test_default_values(self) -> None:
        deps = ConsistencyDeps()
        assert deps.language == "en"
        assert deps.novel_id == ""
        assert deps.existing_issue_count == 0

    def test_custom_values(self) -> None:
        deps = ConsistencyDeps(
            language="de",
            novel_id="novel-abc-123",
            chapter_texts={"ch1": "Am Anfang war das Licht."},
            kb_entity_summaries=[
                {"entity_type": "character", "name": "Elena", "traits": ["brave"]}
            ],
            check_types=[ConsistencyCheckType.CHARACTER, ConsistencyCheckType.PLOT],
            existing_issue_count=3,
        )
        assert deps.language == "de"
        assert deps.novel_id == "novel-abc-123"
        assert "ch1" in deps.chapter_texts
        assert deps.existing_issue_count == 3

    def test_chapter_texts_default_empty(self) -> None:
        assert ConsistencyDeps().chapter_texts == {}

    def test_check_types_defaults_to_all(self) -> None:
        assert ConsistencyDeps().check_types == list(ConsistencyCheckType)


# --- E. ConsistencyOutput — container ---


class TestConsistencyOutput:
    """ConsistencyOutput with issues list, assessment, and checked types."""

    def test_empty_output(self) -> None:
        output = ConsistencyOutput()
        assert output.issues == []
        assert output.overall_assessment == ""
        assert output.checked_types == []

    def test_output_with_issues(self) -> None:
        issues = [
            _make_issue(
                description="Anna's eye color contradicts between chapters.",
                conflicting_facts=["Green eyes", "Blue eyes"],
                confidence=0.95,
            ),
            ConsistencyIssue(
                check_type=ConsistencyCheckType.TIMELINE,
                severity=ConsistencySeverity.WARNING,
                description="Battle of Thornfield dated inconsistently.",
                locations=["Chapter 5", "KB: Events"],
                conflicting_facts=["Spring equinox", "Midsummer"],
                suggestion="Align battle date to spring equinox.",
                confidence=0.7,
            ),
        ]
        output = ConsistencyOutput(
            issues=issues,
            overall_assessment="One critical contradiction and one likely inconsistency found.",
            checked_types=[ConsistencyCheckType.CHARACTER, ConsistencyCheckType.TIMELINE],
        )
        assert len(output.issues) == 2
        assert output.issues[0].severity == ConsistencySeverity.ERROR
        assert output.issues[1].suggestion is not None
        assert ConsistencyCheckType.CHARACTER in output.checked_types


# --- F. Serialization round-trip ---


class TestSerialization:
    """Round-trip serialization via model_dump / model_validate."""

    def test_roundtrip_issue(self) -> None:
        original = _make_issue(
            check_type=ConsistencyCheckType.PLOT,
            severity=ConsistencySeverity.WARNING,
            description="Peter's motivation for betrayal is unclear.",
            conflicting_facts=[
                "Peter swore loyalty to Elena in Ch.8",
                "Peter betrays Elena in Ch.12",
            ],
            suggestion="Seed Peter's motives earlier.",
            confidence=0.65,
        )
        restored = ConsistencyIssue.model_validate(original.model_dump())
        assert restored.check_type == original.check_type
        assert restored.severity == original.severity
        assert restored.description == original.description
        assert restored.suggestion == original.suggestion

    def test_roundtrip_output(self) -> None:
        original = ConsistencyOutput(
            issues=[
                _make_issue(
                    check_type=ConsistencyCheckType.WORLD,
                    severity=ConsistencySeverity.INFO,
                    description="The Silver Forest has different tree species across chapters.",
                    conflicting_facts=["Oak trees", "Pine trees"],
                    confidence=0.5,
                )
            ],
            overall_assessment="Minor world-building discrepancy detected.",
            checked_types=[ConsistencyCheckType.WORLD],
        )
        restored = ConsistencyOutput.model_validate(original.model_dump())
        assert len(restored.issues) == 1
        assert restored.issues[0].check_type == ConsistencyCheckType.WORLD
        assert restored.overall_assessment == original.overall_assessment
        assert restored.checked_types == original.checked_types


# --- G. Enriched ConsistencyDeps (ADR-044) ---


class TestEnrichedConsistencyDeps:
    """ConsistencyDeps with optional structured Stage 1 data (ADR-044)."""

    def test_extracted_facts_default_none(self) -> None:
        """extracted_facts defaults to None (backward-compatible)."""
        deps = ConsistencyDeps()
        assert deps.extracted_facts is None

    def test_timeline_envelopes_default_none(self) -> None:
        """timeline_envelopes defaults to None (backward-compatible)."""
        deps = ConsistencyDeps()
        assert deps.timeline_envelopes is None

    def test_has_structured_input_false_when_none(self) -> None:
        deps = ConsistencyDeps()
        assert not deps.has_structured_input

    def test_has_structured_input_false_when_empty_list(self) -> None:
        deps = ConsistencyDeps(extracted_facts=[])
        assert not deps.has_structured_input

    def test_has_structured_input_true_when_facts_present(self) -> None:
        fact = ExtractedFact(
            fact_type="character_state",
            subject="Anna",
            predicate="has eye color",
            object_value="green",
            chapter_id="ch-1",
            evidence_text="Anna's green eyes sparkled.",
            confidence=0.9,
        )
        deps = ConsistencyDeps(extracted_facts=[fact])
        assert deps.has_structured_input

    def test_enriched_deps_with_both(self) -> None:
        """Both extracted_facts and timeline_envelopes can be provided."""
        fact = ExtractedFact(
            fact_type="event",
            subject="Anna",
            predicate="arrived at",
            object_value="The Tower",
            chapter_id="ch-2",
            evidence_text="Anna pushed open the gate.",
            confidence=0.85,
        )
        envelope = TimelineEventEnvelope(
            event_id="evt-1",
            event_name="Arrival",
            timestamp_raw="day 3",
        )
        deps = ConsistencyDeps(
            language="en",
            novel_id="novel-123",
            extracted_facts=[fact],
            timeline_envelopes=[envelope],
        )
        assert deps.has_structured_input
        assert deps.extracted_facts is not None
        assert len(deps.extracted_facts) == 1
        assert deps.timeline_envelopes is not None
        assert len(deps.timeline_envelopes) == 1
        assert deps.timeline_envelopes[0].event_name == "Arrival"

    def test_backward_compatible_construction(self) -> None:
        """Existing construction without new fields still works."""
        deps = ConsistencyDeps(
            language="de",
            novel_id="test-novel",
            chapter_texts={"ch1": "Am Anfang war das Licht."},
            kb_entity_summaries=[{"entity_type": "character", "name": "Elena"}],
            check_types=[ConsistencyCheckType.CHARACTER],
            existing_issue_count=2,
        )
        assert deps.language == "de"
        assert deps.extracted_facts is None
        assert deps.timeline_envelopes is None
        assert not deps.has_structured_input
        assert deps.existing_issue_count == 2
