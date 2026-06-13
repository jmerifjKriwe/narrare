"""ADR-044 staged consistency Pydantic Evals dataset."""

from __future__ import annotations

from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import IsInstance

from evals.consistency_models import StagedConsistencyInput, StagedConsistencyResult
from evals.evaluators import (
    ContradictionRecall,
    FactExtractionPrecision,
    FactExtractionRecall,
    FalsePositiveGuard,
)
from narrare_core.agents.fact_extractor_types import ExtractedFact, FactType, TimelineEventEnvelope


def build_dataset() -> Dataset[StagedConsistencyInput, StagedConsistencyResult, dict[str, Any]]:
    """Build eval cases for ADR-044 staged consistency quality."""

    return Dataset(
        name="consistency_staged",
        cases=[
            _fact_extraction_case(),
            _consistency_comparison_case(),
            _end_to_end_case(),
        ],
        evaluators=[
            IsInstance(type_name="StagedConsistencyResult"),
            FactExtractionRecall(),
            FactExtractionPrecision(),
            ContradictionRecall(),
            FalsePositiveGuard(),
        ],
    )


def _fact_extraction_case() -> Case[
    StagedConsistencyInput, StagedConsistencyResult, dict[str, Any]
]:
    expected_facts = [
        _expected_fact("Liora", "left", "Stonebridge at dawn on First Thaw"),
        _expected_fact("Liora", "carried", "brass compass"),
        _expected_fact("Liora", "reached", "North Beacon at sunset on First Thaw"),
        _expected_fact("Captain Vale", "stayed", "Stonebridge"),
    ]
    return Case(
        name="stage1-extracts-temporal-and-object-facts",
        inputs=StagedConsistencyInput(
            stage="fact_extraction",
            chapter_texts={
                "ch1": (
                    "At dawn on First Thaw, Liora left Stonebridge with Captain Vale. "
                    "She carried the brass compass wrapped in oilcloth."
                ),
                "ch2": (
                    "By sunset of the same day, Liora reached the North Beacon after "
                    "a two-hour ride. Vale stayed behind at Stonebridge to guard the gate."
                ),
            },
            kb_entity_names=["Liora", "Captain Vale", "Stonebridge", "North Beacon"],
            genre="Fantasy",
        ),
        expected_output=None,
        metadata={"expected_facts": expected_facts},
    )


def _consistency_comparison_case() -> Case[
    StagedConsistencyInput, StagedConsistencyResult, dict[str, Any]
]:
    departure = _timeline_event(
        event_id="evt-departure",
        event_name="Liora leaves Stonebridge",
        timestamp_raw="First Thaw, dawn",
        temporal_order=2,
        source_chapter_id="ch1",
        character="Liora",
        location="Stonebridge",
    )
    impossible_arrival = _timeline_event(
        event_id="evt-arrival",
        event_name="Liora reaches North Beacon",
        timestamp_raw="First Thaw, before dawn",
        temporal_order=1,
        source_chapter_id="ch2",
        character="Liora",
        location="North Beacon",
    )
    return Case(
        name="stage2-detects-reversed-temporal-order",
        inputs=StagedConsistencyInput(
            stage="consistency_comparison",
            extracted_facts=[
                _fact("event", "Liora", "left", "Stonebridge at dawn on First Thaw", "ch1"),
                _fact("event", "Liora", "reached", "North Beacon before dawn on First Thaw", "ch2"),
            ],
            timeline_envelopes=[departure, impossible_arrival],
        ),
        expected_output=None,
        metadata={
            "expected_issue_keywords": [["Liora", "North Beacon", "before dawn", "Stonebridge"]]
        },
    )


def _end_to_end_case() -> Case[StagedConsistencyInput, StagedConsistencyResult, dict[str, Any]]:
    return Case(
        name="e2e-detects-temporal-contradiction-without-cloak-false-positive",
        inputs=StagedConsistencyInput(
            stage="end_to_end",
            chapter_texts={
                "ch1": (
                    "Mira locked the Observatory at midnight and slipped the only brass key "
                    "onto a chain beneath her black cloak. The cloak looked almost gray in "
                    "the fog, but Mira knew it was the same black wool she always wore."
                ),
                "ch2": (
                    "At dawn, Dax was still bargaining in Harbor Market. The road from "
                    "Harbor Market to the Observatory is a six-hour ride on a fresh horse."
                ),
                "ch3": (
                    "At sunrise, only minutes after leaving Harbor Market, Dax appeared "
                    "inside the locked Observatory and called Mira's name."
                ),
            },
            kb_entity_names=["Mira", "Dax", "Observatory", "Harbor Market"],
            genre="Mystery",
        ),
        expected_output=None,
        metadata={
            "expected_issue_keywords": [["Dax", "Harbor Market", "Observatory", "sunrise"]],
            "forbidden_issue_keywords": [["cloak", "black", "gray"]],
        },
    )


def _expected_fact(subject: str, predicate: str, object_value: str) -> dict[str, str]:
    return {"subject": subject, "predicate": predicate, "object_value": object_value}


def _fact(
    fact_type: FactType,
    subject: str,
    predicate: str,
    object_value: str,
    chapter_id: str,
) -> ExtractedFact:
    return ExtractedFact(
        fact_type=fact_type,
        subject=subject,
        predicate=predicate,
        object_value=object_value,
        chapter_id=chapter_id,
        evidence_text=f"{subject} {predicate} {object_value}",
        confidence=0.95,
    )


def _timeline_event(
    *,
    event_id: str,
    event_name: str,
    timestamp_raw: str,
    temporal_order: int,
    source_chapter_id: str,
    character: str,
    location: str,
) -> TimelineEventEnvelope:
    return TimelineEventEnvelope(
        event_id=event_id,
        event_name=event_name,
        timestamp_raw=timestamp_raw,
        temporal_order=temporal_order,
        source_chapter_id=source_chapter_id,
        character_refs=[{"id": character.casefold(), "name": character, "status": "active"}],
        location_ref={
            "id": location.casefold().replace(" ", "-"),
            "name": location,
            "status": "active",
        },
        confidence=0.95,
        is_confirmed=True,
    )
