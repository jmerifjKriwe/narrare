"""Tests for FactExtractorAgent types — validation, defaults, provenance.

See ADR-044 — Staged Multi-Agent Consistency Pipeline.

Test strategy:
- Pydantic model validation for ExtractedFact and TimelineEventEnvelope
- Plain class defaults for FactExtractorDeps
- Protocol compliance check
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from narrare_core.agents.fact_extractor_types import (
    ExtractedFact,
    FactExtractorDeps,
    FactExtractorOutput,
    FactExtractorProtocol,
    TimelineEventEnvelope,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fact(**overrides: object) -> ExtractedFact:
    """Build a valid ExtractedFact with sensible defaults."""
    defaults: dict[str, object] = {
        "fact_type": "character_state",
        "subject": "Anna",
        "predicate": "has eye color",
        "object_value": "green",
        "chapter_id": "ch-1",
        "evidence_text": "Anna's green eyes sparkled.",
        "confidence": 0.9,
        "temporal_marker": None,
    }
    defaults.update(overrides)
    return ExtractedFact(**defaults)  # type: ignore[arg-type]


def _make_envelope(**overrides: object) -> TimelineEventEnvelope:
    """Build a valid TimelineEventEnvelope with sensible defaults."""
    defaults: dict[str, object] = {
        "event_id": "evt-1",
        "event_name": "Battle of Thornfield",
        "timestamp_raw": "spring equinox",
        "timestamp_normalized": "2024-03-20",
        "temporal_order": 5,
        "source_chapter_id": "ch-3",
        "character_refs": [{"id": "char-1", "name": "Anna", "status": "active"}],
        "location_ref": {"id": "loc-1", "name": "Thornfield", "status": "active"},
        "causes": ["Anna declared war"],
        "consequences": ["Anna gained territory"],
        "source": "narration",
        "confidence": 0.95,
        "is_confirmed": True,
        "kb_entity_status": {"Anna": "active"},
    }
    defaults.update(overrides)
    return TimelineEventEnvelope(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. ExtractedFact — creation + validation
# ---------------------------------------------------------------------------


class TestExtractedFact:
    """ExtractedFact with fact_type, subject, predicate, object_value, provenance."""

    def test_basic_fact_creation(self) -> None:
        fact = _make_fact()
        assert fact.fact_type == "character_state"
        assert fact.subject == "Anna"
        assert fact.predicate == "has eye color"
        assert fact.object_value == "green"
        assert fact.chapter_id == "ch-1"
        assert fact.evidence_text == "Anna's green eyes sparkled."
        assert fact.confidence == 0.9
        assert fact.temporal_marker is None

    def test_all_fact_types(self) -> None:
        """All six fact types are valid."""
        for ft in (
            "character_state",
            "event",
            "location_state",
            "relationship",
            "ability",
            "timeline_marker",
        ):
            fact = _make_fact(fact_type=ft)
            assert fact.fact_type == ft

    def test_invalid_fact_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_fact(fact_type="invalid_type")

    def test_confidence_validation_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            _make_fact(confidence=-0.1)

    def test_confidence_validation_rejects_over_one(self) -> None:
        with pytest.raises(ValidationError):
            _make_fact(confidence=1.5)

    def test_confidence_boundary_zero(self) -> None:
        fact = _make_fact(confidence=0.0)
        assert fact.confidence == 0.0

    def test_confidence_boundary_one(self) -> None:
        fact = _make_fact(confidence=1.0)
        assert fact.confidence == 1.0

    def test_temporal_marker_optional(self) -> None:
        fact = _make_fact(temporal_marker="before the battle")
        assert fact.temporal_marker == "before the battle"

    def test_temporal_marker_none_default(self) -> None:
        fact = _make_fact()
        assert fact.temporal_marker is None

    def test_required_fields_missing(self) -> None:
        """Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            ExtractedFact(  # pyright: ignore[reportCallIssue]
                fact_type="event",
                subject="Anna",
                # Missing: predicate, object_value, chapter_id, evidence_text
            )

    def test_event_fact(self) -> None:
        fact = _make_fact(
            fact_type="event",
            subject="Anna",
            predicate="arrived at",
            object_value="The Tower",
            evidence_text="Anna pushed open the heavy iron gate.",
            temporal_marker="at dusk",
        )
        assert fact.fact_type == "event"
        assert fact.temporal_marker == "at dusk"

    def test_relationship_fact(self) -> None:
        fact = _make_fact(
            fact_type="relationship",
            subject="Anna",
            predicate="is allied with",
            object_value="Marcus",
            evidence_text="Anna and Marcus stood side by side.",
        )
        assert fact.fact_type == "relationship"


# ---------------------------------------------------------------------------
# B. TimelineEventEnvelope — provenance preservation
# ---------------------------------------------------------------------------


class TestTimelineEventEnvelope:
    """TimelineEventEnvelope preserves FIND-009 provenance metadata."""

    def test_basic_envelope_creation(self) -> None:
        env = _make_envelope()
        assert env.event_id == "evt-1"
        assert env.event_name == "Battle of Thornfield"
        assert env.timestamp_raw == "spring equinox"
        assert env.timestamp_normalized == "2024-03-20"
        assert env.temporal_order == 5
        assert env.source_chapter_id == "ch-3"
        assert len(env.character_refs) == 1
        assert env.character_refs[0]["name"] == "Anna"
        assert env.location_ref is not None
        assert env.location_ref["name"] == "Thornfield"
        assert len(env.causes) == 1
        assert len(env.consequences) == 1
        assert env.source == "narration"
        assert env.confidence == 0.95
        assert env.is_confirmed is True
        assert env.kb_entity_status == {"Anna": "active"}

    def test_minimal_envelope(self) -> None:
        """Only event_id, event_name, and timestamp_raw are required."""
        env = TimelineEventEnvelope(
            event_id="evt-2",
            event_name="Arrival",
            timestamp_raw="day 3",
        )
        assert env.event_id == "evt-2"
        assert env.timestamp_normalized is None
        assert env.temporal_order is None
        assert env.source_chapter_id is None
        assert env.character_refs == []
        assert env.location_ref is None
        assert env.causes == []
        assert env.consequences == []
        assert env.source is None
        assert env.confidence == 1.0  # default
        assert env.is_confirmed is True  # default
        assert env.kb_entity_status == {}

    def test_confidence_validation(self) -> None:
        with pytest.raises(ValidationError):
            _make_envelope(confidence=2.0)
        with pytest.raises(ValidationError):
            _make_envelope(confidence=-0.5)

    def test_kb_entity_status_values(self) -> None:
        """kb_entity_status maps entity names to valid status values."""
        env = _make_envelope(
            kb_entity_status={
                "Anna": "active",
                "The Tower": "renamed",
                "Old Village": "deprecated",
                "Dark Forest": "deleted",
            },
        )
        assert env.kb_entity_status["Anna"] == "active"
        assert env.kb_entity_status["The Tower"] == "renamed"
        assert env.kb_entity_status["Old Village"] == "deprecated"
        assert env.kb_entity_status["Dark Forest"] == "deleted"

    def test_character_refs_structure(self) -> None:
        env = _make_envelope(
            character_refs=[
                {"id": "c1", "name": "Anna", "status": "active"},
                {"id": "c2", "name": "Marcus", "status": "deprecated"},
            ],
        )
        assert len(env.character_refs) == 2
        assert env.character_refs[1]["name"] == "Marcus"

    def test_location_ref_structure(self) -> None:
        env = _make_envelope(location_ref=None)
        assert env.location_ref is None

        env2 = _make_envelope(location_ref={"id": "l1", "name": "Tower", "status": "active"})
        assert env2.location_ref is not None
        assert env2.location_ref["name"] == "Tower"

    def test_causes_and_consequences(self) -> None:
        env = _make_envelope(
            causes=["cause1", "cause2"],
            consequences=["consequence1"],
        )
        assert len(env.causes) == 2
        assert len(env.consequences) == 1


# ---------------------------------------------------------------------------
# C. FactExtractorDeps — defaults and construction
# ---------------------------------------------------------------------------


class TestFactExtractorDeps:
    """FactExtractorDeps plain class with sensible defaults."""

    def test_default_values(self) -> None:
        deps = FactExtractorDeps()
        assert deps.chapter_texts == {}
        assert deps.kb_entity_names == []
        assert deps.kb_entity_summaries == []
        assert deps.timeline_envelopes == []
        assert deps.language == "en"
        assert deps.genre == ""

    def test_custom_values(self) -> None:
        envelope = _make_envelope()
        deps = FactExtractorDeps(
            chapter_texts={"ch1": "Anna walked."},
            kb_entity_names=["Anna", "The Tower"],
            kb_entity_summaries=[{"entity_type": "character", "name": "Anna"}],
            timeline_envelopes=[envelope],
            language="de",
            genre="Fantasy",
        )
        assert "ch1" in deps.chapter_texts
        assert len(deps.kb_entity_names) == 2
        assert len(deps.timeline_envelopes) == 1
        assert deps.language == "de"
        assert deps.genre == "Fantasy"

    def test_none_defaults_to_empty(self) -> None:
        deps = FactExtractorDeps(
            chapter_texts=None,
            kb_entity_names=None,
            kb_entity_summaries=None,
            timeline_envelopes=None,
        )
        assert deps.chapter_texts == {}
        assert deps.kb_entity_names == []
        assert deps.kb_entity_summaries == []
        assert deps.timeline_envelopes == []


# ---------------------------------------------------------------------------
# D. FactExtractorOutput — container
# ---------------------------------------------------------------------------


class TestFactExtractorOutput:
    """FactExtractorOutput with facts list and assessment summary."""

    def test_empty_output(self) -> None:
        output = FactExtractorOutput()
        assert output.facts == []
        assert output.assessment_summary == ""

    def test_output_with_facts(self) -> None:
        facts = [
            _make_fact(subject="Anna", predicate="is", object_value="brave"),
            _make_fact(
                fact_type="event",
                subject="Marcus",
                predicate="arrived at",
                object_value="the tower",
            ),
        ]
        output = FactExtractorOutput(
            facts=facts,
            assessment_summary="Extracted 2 facts from chapters ch-1.",
        )
        assert len(output.facts) == 2
        assert "2 facts" in output.assessment_summary


# ---------------------------------------------------------------------------
# E. Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    """Round-trip serialization via model_dump / model_validate."""

    def test_roundtrip_extracted_fact(self) -> None:
        original = _make_fact(
            fact_type="event",
            subject="Marcus",
            predicate="departed from",
            object_value="the village",
            evidence_text="Marcus rode out at dawn.",
            confidence=0.85,
            temporal_marker="at dawn",
        )
        restored = ExtractedFact.model_validate(original.model_dump())
        assert restored.fact_type == original.fact_type
        assert restored.subject == original.subject
        assert restored.temporal_marker == original.temporal_marker

    def test_roundtrip_timeline_envelope(self) -> None:
        original = _make_envelope(
            event_name="The Council",
            causes=["Anna called the meeting"],
            consequences=["The alliance was formed"],
        )
        restored = TimelineEventEnvelope.model_validate(original.model_dump())
        assert restored.event_name == original.event_name
        assert restored.causes == original.causes

    def test_roundtrip_output(self) -> None:
        original = FactExtractorOutput(
            facts=[_make_fact()],
            assessment_summary="One fact extracted.",
        )
        restored = FactExtractorOutput.model_validate(original.model_dump())
        assert len(restored.facts) == 1
        assert restored.assessment_summary == original.assessment_summary


# ---------------------------------------------------------------------------
# F. Protocol compliance
# ---------------------------------------------------------------------------


class TestFactExtractorProtocol:
    """FactExtractorProtocol is runtime-checkable."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """FactExtractorProtocol can be used with isinstance()."""

        # A class with a compatible run method should satisfy the protocol
        class FakeExtractor:
            async def run(
                self, prompt: str, deps: FactExtractorDeps, **kwargs: object
            ) -> FactExtractorOutput:
                return FactExtractorOutput()

        # Note: runtime_checkable Protocols only check method signatures exist,
        # not their full type signatures.
        assert isinstance(FakeExtractor(), FactExtractorProtocol)

    def test_incompatible_class_fails_check(self) -> None:
        """A class without run() does not satisfy the protocol."""
        assert not isinstance("not an extractor", FactExtractorProtocol)
