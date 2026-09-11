"""Relation scoring: reference relations vs actual relationship edges (Task 11).

An expected relation (R*) matches an actual edge iff BOTH endpoints
resolve through the entity match map (reference entity id → actual
entry id, built by ``entity_match``) onto the edge's ``source_id`` /
``target_id`` AND the predicates match per the enumerated algebra in
``relation_predicates`` (canonical normalization plus the equivalence
tables). The predicate-level rules and their rationale live there;
this module owns the scoring loop over relations and edges.

Direction rules (relaxed from strict directedness for measurement
validity — run 2026-09-07-clean-incremental-3 counted semantically
correct edges missing/spurious purely for orientation):

- Same-direction edges use ``predicates_match``: exact equality, or an
  enumerated gender pair (``GENDER_EQUIVALENCE``) the shared
  subject's corpus gender satisfies; unknown gender stays strict.
- Swapped-endpoint edges (edge source = reference object, edge target
  = reference subject) use ``swapped_predicates_match``: symmetric
  predicates ("A colleague_of B" ≡ "B colleague_of A") and inverse
  kinship pairs (``mother_of(A→B)`` ≡ ``daughter_of(B→A)`` iff A is
  female AND B is female). ``first_grandchild_of`` stays strict —
  birth order has no inverse.
- A relation with ANY unresolved endpoint is ``missing`` immediately
  (no edge can match an unknown id).
- Each edge is claimed at most once: expected relations are processed
  in reference order, edges in listing order; the first unclaimed edge
  satisfying the endpoint + predicate conditions claims it
  (deterministic).
- Unclaimed edges are spurious (itemized with edge id + display names
  for traceability).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from benchmark.scoring.relation_predicates import (
    canonical_relation_predicate,
    predicates_match,
    swapped_predicates_match,
)
from benchmark.scoring.score_records import (
    RelationOutcome,
    RelationStatus,
    SpuriousRelation,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.corpus_views import Entity, Gender, Relation
    from benchmark.drivers.out_records import RelationshipDetail


def person_genders(persons: tuple[Entity, ...]) -> Mapping[str, Gender]:
    """Reference person id → corpus gender; unknown genders are omitted."""
    return {person.id: person.gender for person in persons if person.gender is not None}


@dataclass(frozen=True)
class RelationMatchResult:
    """Expected-relation outcomes plus the unclaimed (spurious) edges."""

    outcomes: tuple[RelationOutcome, ...]
    spurious: tuple[SpuriousRelation, ...]


def score_relations(
    expected: tuple[Relation, ...],
    edges: tuple[RelationshipDetail, ...],
    ref_to_entry: Mapping[str, str],
    person_gender: Mapping[str, Gender],
) -> RelationMatchResult:
    """Score reference relations against relationship edges via the map.

    ``person_gender`` (see ``person_genders``) adjudicates the
    gender-aware equivalences on BOTH sides of a swapped-endpoint
    match — the edge subject there is the reference object, so its
    corpus gender is looked up through the inverse of the match map.
    Persons without a known gender match only exactly.
    """
    entry_gender = _entry_genders(ref_to_entry, person_gender)
    claimed: set[str] = set()
    outcomes: list[RelationOutcome] = []
    for relation in expected:
        matched = _match(
            relation,
            edges,
            ref_to_entry,
            person_gender.get(relation.subject),
            entry_gender,
            claimed,
        )
        if matched is not None:
            claimed.add(matched)
            outcomes.append(_outcome(relation, "found", matched))
        else:
            outcomes.append(_outcome(relation, "missing", None))

    spurious = tuple(
        SpuriousRelation(
            edge_id=edge.id,
            rel_type=edge.rel_type,
            source_name=edge.source_name,
            target_name=edge.target_name,
        )
        for edge in edges
        if edge.id not in claimed
    )
    return RelationMatchResult(outcomes=tuple(outcomes), spurious=spurious)


def _entry_genders(
    ref_to_entry: Mapping[str, str],
    person_gender: Mapping[str, Gender],
) -> dict[str, Gender]:
    """Entry id → corpus gender (inverse of the match map; first ref wins).

    Feeds the swapped-endpoint predicate check: there the EDGE subject
    is the reference object. Entries without a gendered reference
    person contribute nothing (unknown gender stays strict).
    """
    entry_gender: dict[str, Gender] = {}
    for ref_id, entry_id in ref_to_entry.items():
        gender = person_gender.get(ref_id)
        if gender is not None:
            entry_gender.setdefault(entry_id, gender)
    return entry_gender


def _match(
    relation: Relation,
    edges: tuple[RelationshipDetail, ...],
    ref_to_entry: Mapping[str, str],
    subject_gender: Gender | None,
    entry_gender: Mapping[str, Gender],
    claimed: set[str],
) -> str | None:
    source = ref_to_entry.get(relation.subject)
    target = ref_to_entry.get(relation.object)
    if source is None or target is None:
        return None
    predicate = canonical_relation_predicate(relation.predicate)
    for edge in edges:
        if edge.id in claimed:
            continue
        edge_predicate = canonical_relation_predicate(edge.rel_type)
        same_direction = edge.source_id == source and edge.target_id == target
        swapped = edge.source_id == target and edge.target_id == source
        if same_direction and predicates_match(predicate, edge_predicate, subject_gender):
            return edge.id
        if swapped and swapped_predicates_match(
            predicate,
            edge_predicate,
            subject_gender,
            entry_gender.get(edge.source_id),
        ):
            return edge.id
    return None


def _outcome(relation: Relation, status: RelationStatus, matched: str | None) -> RelationOutcome:
    return RelationOutcome(
        ref_id=relation.id,
        subject=relation.subject,
        predicate=relation.predicate,
        object=relation.object,
        status=status,
        matched_edge_id=matched,
    )
