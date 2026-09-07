"""Build-quality scoring facade: reference vs fetched KB state (Task 11).

``score_build_quality`` composes the three matchers over the
OUT-direction records (CAP-OUT-01 browse listing + CAP-OUT-03
per-entity details) into the typed ``BuildQualityScore``:

- expected entities = persons + places + objects, in reference order;
- expected facts follow their entities (F / PF / OF ids);
- relations are scored against the edge set collected from ALL detail
  records, deduplicated by edge id (the same edge appears on both
  endpoint fetches; first occurrence wins);
- a matched entity WITHOUT a fetched detail scores its facts as
  ``missing`` — the detail fetch is the only fact-evidence source, and
  absence is reported honestly, never fabricated.

Pure and deterministic: no clocks, no randomness (plan Global
Constraints). Events are NOT scored here — they are a Task 13
retrieval surface. Aggregate conventions are documented on
``BuildQualityScore``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmark.scoring.entity_match import EntityMatch, EntityMatchResult, match_entities
from benchmark.scoring.fact_match import actual_facts_from, score_facts, spurious_facts
from benchmark.scoring.relation_match import person_genders, score_relations
from benchmark.scoring.score_records import (
    BuildQualityScore,
    EntityOutcome,
    FactOutcome,
    SpuriousEntity,
    SpuriousFact,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.corpus_views import Entity, Reference
    from benchmark.drivers.out_records import (
        EntityDetailRecord,
        EntrySummary,
        RelationshipDetail,
    )


def score_build_quality(
    reference: Reference,
    entries: tuple[EntrySummary, ...],
    details: tuple[EntityDetailRecord, ...],
) -> BuildQualityScore:
    """Score the ingested KB build against the clean-corpus reference."""
    expected = reference.persons + reference.places + reference.objects
    entity_result = match_entities(expected, entries)
    ref_to_entry = {match.ref.id: match.entry.id for match in entity_result.matches}
    details_by_entry: dict[str, EntityDetailRecord] = {}
    for record in details:
        details_by_entry.setdefault(record.entry.id, record)

    entity_outcomes: list[EntityOutcome] = []
    fact_outcomes: list[FactOutcome] = []
    spurious_fact_rows: list[SpuriousFact] = []
    residence_index = _residence_index(entity_result, details_by_entry)
    for ref in expected:
        entity_outcomes.append(
            _entity_outcome(
                ref,
                entity_result,
                details_by_entry,
                residence_index,
                fact_outcomes,
                spurious_fact_rows,
            )
        )

    relation_result = score_relations(
        reference.relations,
        _dedupe_edges(details),
        ref_to_entry,
        person_genders(reference.persons),
    )

    expected_facts = len(fact_outcomes)
    found_facts = sum(1 for fact in fact_outcomes if fact.status != "missing")
    correct_facts = sum(1 for fact in fact_outcomes if fact.status == "found")
    found_entities = sum(1 for entity in entity_outcomes if entity.status == "found")
    found_relations = sum(1 for relation in relation_result.outcomes if relation.status == "found")
    return BuildQualityScore(
        entity_coverage=found_entities / len(expected) if expected else 0.0,
        fact_coverage=found_facts / expected_facts if expected_facts else 0.0,
        fact_precision=correct_facts / found_facts if found_facts else None,
        relation_coverage=(
            found_relations / len(reference.relations) if reference.relations else 0.0
        ),
        entities=tuple(entity_outcomes),
        facts=tuple(fact_outcomes),
        relations=relation_result.outcomes,
        spurious_entities=tuple(
            SpuriousEntity(entry_id=entry.id, name=entry.name) for entry in entity_result.spurious
        ),
        spurious_facts=tuple(spurious_fact_rows),
        spurious_relations=relation_result.spurious,
    )


def _residence_index(
    entity_result: EntityMatchResult,
    details_by_entry: dict[str, EntityDetailRecord],
) -> dict[str, Mapping[str, object]]:
    """Reference entity id → matched entry metadata (inverse residence evidence).

    Feeds the fact matcher's inverse residence rule (round 3): a place
    fact ``residence_of: <person id>`` consults the person entry's
    residence keys. Entries without a fetched detail contribute nothing
    (absence is reported honestly, never fabricated).
    """
    return {
        match.ref.id: actual_facts_from(details_by_entry[match.entry.id].entry).metadata
        for match in entity_result.matches
        if match.entry.id in details_by_entry
    }


def _entity_outcome(
    ref: Entity,
    entity_result: EntityMatchResult,
    details_by_entry: dict[str, EntityDetailRecord],
    residence_index: dict[str, Mapping[str, object]],
    fact_outcomes: list[FactOutcome],
    spurious_fact_rows: list[SpuriousFact],
) -> EntityOutcome:
    """Score one expected entity; append its fact outcomes in reference order."""
    matched = _lookup_match(entity_result, ref.id)
    entry_id = matched.entry.id if matched else None
    detail = details_by_entry.get(entry_id) if entry_id is not None else None
    if matched is not None and detail is not None:
        actual = actual_facts_from(detail.entry)
        facts = score_facts(ref, actual, residence_index)
        spurious_fact_rows.extend(spurious_facts(ref, actual, matched.entry.id, ref.name))
    else:
        facts = tuple(
            FactOutcome(
                ref_id=fact.id,
                entity_ref_id=ref.id,
                predicate=fact.predicate,
                value=fact.value,
                status="missing",
                evidence=None,
            )
            for fact in ref.facts
        )
    fact_outcomes.extend(facts)
    found = sum(1 for fact in facts if fact.status != "missing")
    correct = sum(1 for fact in facts if fact.status == "found")
    return EntityOutcome(
        ref_id=ref.id,
        ref_name=ref.name,
        status="found" if matched is not None else "missing",
        matched_entry_id=entry_id,
        matched_via=matched.via if matched else None,
        facts_expected=len(ref.facts),
        facts_found=found,
        facts_correct=correct,
    )


def _dedupe_edges(details: tuple[EntityDetailRecord, ...]) -> tuple[RelationshipDetail, ...]:
    """Collect relationship edges across details; first occurrence wins."""
    seen: set[str] = set()
    edges: list[RelationshipDetail] = []
    for record in details:
        for edge in record.relationships:
            if edge.id not in seen:
                seen.add(edge.id)
                edges.append(edge)
    return tuple(edges)


def _lookup_match(entity_result: EntityMatchResult, ref_id: str) -> EntityMatch | None:
    """Find the match row for a reference id (matches are few; linear scan)."""
    for match in entity_result.matches:
        if match.ref.id == ref_id:
            return match
    return None
