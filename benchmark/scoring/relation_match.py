"""Relation scoring: reference relations vs actual relationship edges (Task 11).

An expected relation (R*) matches an actual edge iff BOTH endpoints
resolve through the entity match map (reference entity id → actual
entry id, built by ``entity_match``) onto the edge's ``source_id`` /
``target_id`` AND the predicates are equal after canonical
normalization (``canonical_relation_predicate``: snake_case
normalization plus folding of bare role/kinship surfaces onto their
canonical ``_of``-suffixed registry predicate — "mother" →
"mother_of"). Beyond exact equality, the enumerated gender-aware
kinship equivalences (``GENDER_EQUIVALENCE``) fold a generic predicate
onto its gendered counterpart — ``parent_of`` ≡ ``father_of`` for a
male subject — iff the shared subject's corpus gender agrees with the
gendered side; unknown gender stays strict. Other semantic synonyms are
deliberately NOT folded ("colleague_of" ≠ "neighbor_of"): vocabulary
alignment happens in the extraction prompt, not in scorer leniency.

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
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from benchmark.scoring.normalize import normalize_predicate
from benchmark.scoring.score_records import (
    RelationOutcome,
    RelationStatus,
    SpuriousRelation,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.corpus_views import Entity, Gender, Relation
    from benchmark.drivers.out_records import RelationshipDetail

RELATION_ALIASES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "babysitter": "babysitter_of",
        "business_partner": "business_partner_of",
        "colleague": "colleague_of",
        "father": "father_of",
        "first_grandchild": "first_grandchild_of",
        "grandmother": "grandmother_of",
        "half_sibling": "half_sibling_of",
        "keeper": "keeper_of",
        "mother": "mother_of",
        "neighbor": "neighbor_of",
        "property_manager": "property_manager_of",
        "sibling": "sibling_of",
        "son": "son_of",
        "spouse": "spouse_of",
    }
)
"""Folding of bare role/kinship surfaces onto the canonical
``_of``-suffixed registry predicate (the
``benchmark/corpus/reference/relations.yaml`` forms). Canonical forms
and unknown predicates pass through unchanged; there is deliberately no
semantic synonym folding in THIS table (``brother_of`` never becomes
``sibling_of`` here). Mirrors the canonical registry in
``narrare_core.kb.predicates`` (which the benchmark must not import —
co-evolution boundary)."""

GENDER_EQUIVALENCE: Final[Mapping[frozenset[str], Gender]] = MappingProxyType(
    {
        frozenset({"parent_of", "father_of"}): "male",
        frozenset({"parent_of", "mother_of"}): "female",
        frozenset({"child_of", "son_of"}): "male",
        frozenset({"child_of", "daughter_of"}): "female",
        frozenset({"grandparent_of", "grandfather_of"}): "male",
        frozenset({"grandparent_of", "grandmother_of"}): "female",
        frozenset({"sibling_of", "brother_of"}): "male",
        frozenset({"sibling_of", "sister_of"}): "female",
    }
)
"""Gender-aware kinship equivalence pairs (enumerated, closed set).

Key = one canonical predicate pair (generic side + gendered side);
value = the subject gender the pair's gendered predicate requires
(``father_of`` ⇒ male, ``mother_of`` ⇒ female, …). A reference relation
and an edge whose canonical predicates form such a pair match IFF the
shared subject resolves to that corpus gender (either direction — the
pair lookup is symmetric); an unknown/absent gender stays strict. Two
gendered predicates are never equivalent (``father_of`` ≠
``mother_of``), and ``grandchild_of`` vs ``first_grandchild_of`` is
deliberately absent (different roles, not a gender pair)."""


def canonical_relation_predicate(value: str) -> str:
    """Normalize a relationship predicate to the canonical registry form.

    Snake_case normalization first, then folding of documented bare
    surfaces onto their canonical ``_of`` form. Unknown predicates are
    returned normalized but unfolded.
    """
    predicate = normalize_predicate(value)
    return RELATION_ALIASES.get(predicate, predicate)


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
    gender-aware kinship equivalences; persons without a known gender
    match only exactly.
    """
    claimed: set[str] = set()
    outcomes: list[RelationOutcome] = []
    for relation in expected:
        matched = _match(
            relation,
            edges,
            ref_to_entry,
            person_gender.get(relation.subject),
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


def _match(
    relation: Relation,
    edges: tuple[RelationshipDetail, ...],
    ref_to_entry: Mapping[str, str],
    subject_gender: Gender | None,
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
        if edge.source_id != source or edge.target_id != target:
            continue
        edge_predicate = canonical_relation_predicate(edge.rel_type)
        if _predicates_match(predicate, edge_predicate, subject_gender):
            return edge.id
    return None


def _predicates_match(
    reference_predicate: str,
    edge_predicate: str,
    subject_gender: Gender | None,
) -> bool:
    """Exact equality, or an enumerated gender pair the subject satisfies."""
    if reference_predicate == edge_predicate:
        return True
    required = GENDER_EQUIVALENCE.get(frozenset((reference_predicate, edge_predicate)))
    return required is not None and subject_gender == required


def _outcome(relation: Relation, status: RelationStatus, matched: str | None) -> RelationOutcome:
    return RelationOutcome(
        ref_id=relation.id,
        subject=relation.subject,
        predicate=relation.predicate,
        object=relation.object,
        status=status,
        matched_edge_id=matched,
    )
