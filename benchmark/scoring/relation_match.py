"""Relation scoring: reference relations vs actual relationship edges (Task 11).

An expected relation (R*) matches an actual edge iff BOTH endpoints
resolve through the entity match map (reference entity id → actual
entry id, built by ``entity_match``) onto the edge's ``source_id`` /
``target_id`` AND the predicates are equal after
``normalize_predicate`` (snake_case normalization).

Tolerance rules (documented v1 behavior):

- Matching is DIRECTED. An edge with swapped endpoints counts as
  missing — the KB's inverse rel types are not enumerable without the
  per-type inverse lookup, and direction-swapped inverses would need a
  lossless inverse table the KB does not expose globally.
- A relation with ANY unresolved endpoint is ``missing`` immediately
  (no edge can match an unknown id).
- Each edge is claimed at most once: expected relations are processed
  in reference order, edges in listing order; the first unclaimed edge
  satisfying all three conditions claims it (deterministic).
- Unclaimed edges are spurious (itemized with edge id + display names
  for traceability).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from benchmark.scoring.normalize import normalize_predicate
from benchmark.scoring.score_records import (
    RelationOutcome,
    RelationStatus,
    SpuriousRelation,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.corpus_views import Relation
    from benchmark.drivers.out_records import RelationshipDetail


@dataclass(frozen=True)
class RelationMatchResult:
    """Expected-relation outcomes plus the unclaimed (spurious) edges."""

    outcomes: tuple[RelationOutcome, ...]
    spurious: tuple[SpuriousRelation, ...]


def score_relations(
    expected: tuple[Relation, ...],
    edges: tuple[RelationshipDetail, ...],
    ref_to_entry: Mapping[str, str],
) -> RelationMatchResult:
    """Score reference relations against relationship edges via the map."""
    claimed: set[str] = set()
    outcomes: list[RelationOutcome] = []
    for relation in expected:
        matched = _match(relation, edges, ref_to_entry, claimed)
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


def _match(
    relation: Relation,
    edges: tuple[RelationshipDetail, ...],
    ref_to_entry: Mapping[str, str],
    claimed: set[str],
) -> str | None:
    source = ref_to_entry.get(relation.subject)
    target = ref_to_entry.get(relation.object)
    if source is None or target is None:
        return None
    predicate = normalize_predicate(relation.predicate)
    for edge in edges:
        if edge.id in claimed:
            continue
        if (
            edge.source_id == source
            and edge.target_id == target
            and normalize_predicate(edge.rel_type) == predicate
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
