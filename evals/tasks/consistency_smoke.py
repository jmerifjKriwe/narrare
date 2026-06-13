"""Deterministic smoke task for ADR-044 staged consistency evals."""

from __future__ import annotations

from evals.consistency_models import StagedConsistencyInput, StagedConsistencyResult
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyIssue,
    ConsistencySeverity,
)
from narrare_core.agents.fact_extractor_types import ExtractedFact, FactType, TimelineEventEnvelope


async def consistency_staged_task(inputs: object) -> object:
    """Run the CI-safe staged consistency smoke task."""

    return await consistency_staged(StagedConsistencyInput.model_validate(inputs))


async def consistency_staged(inputs: StagedConsistencyInput) -> StagedConsistencyResult:
    """Produce deterministic staged consistency output without provider calls."""

    facts = inputs.extracted_facts or _extract_facts(inputs)
    issues: list[ConsistencyIssue] = []
    if inputs.stage in {"consistency_comparison", "end_to_end"}:
        issues = _detect_temporal_issues(facts, inputs.timeline_envelopes)
    return StagedConsistencyResult(
        extracted_facts=facts,
        issues=issues,
        overall_assessment=_assessment(issues),
    )


def _extract_facts(inputs: StagedConsistencyInput) -> list[ExtractedFact]:
    text = "\n".join(inputs.chapter_texts.values()).casefold()
    facts: list[ExtractedFact] = []
    if "first thaw" in text and "stonebridge" in text:
        facts.extend(
            [
                _fact("event", "Liora", "left", "Stonebridge at dawn on First Thaw", "ch1"),
                _fact("ability", "Liora", "carried", "brass compass", "ch1"),
                _fact("event", "Liora", "reached", "North Beacon at sunset on First Thaw", "ch2"),
                _fact("location_state", "Captain Vale", "stayed", "Stonebridge", "ch2"),
            ]
        )
    if "harbor market" in text and "observatory" in text:
        facts.extend(
            [
                _fact("location_state", "Dax", "was at", "Harbor Market at dawn", "ch2"),
                _fact(
                    "timeline_marker",
                    "Harbor Market",
                    "is",
                    "six-hour ride from Observatory",
                    "ch2",
                ),
                _fact(
                    "event",
                    "Dax",
                    "appeared",
                    "inside Observatory at sunrise minutes after leaving Harbor Market",
                    "ch3",
                ),
                _fact("location_state", "Mira's cloak", "appeared", "gray in fog", "ch1"),
            ]
        )
    return facts


def _detect_temporal_issues(
    facts: list[ExtractedFact], timeline_envelopes: list[TimelineEventEnvelope]
) -> list[ConsistencyIssue]:
    issues: list[ConsistencyIssue] = []
    fact_text = " ".join(
        f"{fact.subject} {fact.predicate} {fact.object_value}" for fact in facts
    ).casefold()
    if (
        "liora" in fact_text
        and "north beacon before dawn" in fact_text
        and "stonebridge at dawn" in fact_text
    ) or _has_reversed_liora_timeline(timeline_envelopes):
        issues.append(
            _issue(
                description=(
                    "Liora reaches North Beacon before dawn even though she leaves "
                    "Stonebridge at dawn."
                ),
                locations=["ch1", "ch2"],
                conflicting_facts=[
                    "Liora left Stonebridge at dawn on First Thaw",
                    "Liora reached North Beacon before dawn on First Thaw",
                ],
            )
        )
    if (
        "dax" in fact_text
        and "harbor market at dawn" in fact_text
        and "observatory at sunrise" in fact_text
        and "six-hour ride" in fact_text
    ):
        issues.append(
            _issue(
                description=(
                    "Dax cannot travel from Harbor Market to the Observatory by sunrise "
                    "when the route takes six hours."
                ),
                locations=["ch2", "ch3"],
                conflicting_facts=[
                    "Dax was at Harbor Market at dawn",
                    "Dax appeared inside Observatory at sunrise",
                    "Harbor Market is a six-hour ride from the Observatory",
                ],
            )
        )
    return issues


def _has_reversed_liora_timeline(timeline_envelopes: list[TimelineEventEnvelope]) -> bool:
    departure_order = _event_order(timeline_envelopes, "leaves stonebridge")
    arrival_order = _event_order(timeline_envelopes, "reaches north beacon")
    if departure_order is None or arrival_order is None:
        return False
    return arrival_order < departure_order


def _event_order(timeline_envelopes: list[TimelineEventEnvelope], name: str) -> int | None:
    for envelope in timeline_envelopes:
        if name in envelope.event_name.casefold():
            return envelope.temporal_order
    return None


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


def _issue(
    description: str,
    locations: list[str],
    conflicting_facts: list[str],
) -> ConsistencyIssue:
    return ConsistencyIssue(
        check_type=ConsistencyCheckType.TIMELINE,
        severity=ConsistencySeverity.ERROR,
        description=description,
        locations=locations,
        conflicting_facts=conflicting_facts,
        suggestion="Adjust event timing or travel duration so the sequence is possible.",
        confidence=0.95,
    )


def _assessment(issues: list[ConsistencyIssue]) -> str:
    if issues:
        return f"Found {len(issues)} staged consistency issue(s)."
    return "No staged consistency issues found."
