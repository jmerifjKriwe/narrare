"""Query generation for the retrieval scorer (Task 13).

Deterministic derivation of retrieval queries from the clean-corpus
reference — the mechanical question set the runner asks the OUT
endpoints. Candidates are assembled in reference order (every entity
fact: persons → places → objects, facts in reference order; then every
relation) and sampled with a fixed stride:

    k = max(1, S // N)   (S candidates, sample_size N)
    selection = candidates[0], candidates[k], candidates[2k], …  capped at N

``S ≤ N`` selects ALL candidates. No ``random`` module, no wall clock:
identical references yield identical queries (plan Global Constraints).

Kinds. A fact WITHOUT interval bounds asks ``entity_lookup`` (expected =
the fact value); a fact WITH bounds asks ``state_at_time`` (expected =
the value that held during its OWN bounds — the rider-A material); a
relation asks ``relationship`` (expected = the object entity's name).
Relation endpoints resolve through the reference entity map; an
unresolvable endpoint is registry/reference drift → ``ValueError``
(hard error, never silent — ``detection`` precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.scoring.retrieval_records import RetrievalQuery

if TYPE_CHECKING:
    from benchmark.corpus_views import Entity, Fact, Reference
    from benchmark.scoring.retrieval_records import QueryKind

DEFAULT_SAMPLE_SIZE: Final[int] = 12
"""Default number of sampled queries (plan Task 13: ``N sample facts``)."""

__all__ = [
    "DEFAULT_SAMPLE_SIZE",
    "generate_queries",
]


def generate_queries(
    reference: Reference, sample_size: int = DEFAULT_SAMPLE_SIZE
) -> tuple[RetrievalQuery, ...]:
    """Derive the retrieval queries from the reference (module docstring rules)."""
    if sample_size < 1:
        msg = f"retrieval query generation: sample_size must be >= 1, got {sample_size}"
        raise ValueError(msg)
    candidates = [*_fact_candidates(reference), *_relation_candidates(reference)]
    stride = max(1, len(candidates) // sample_size)
    return tuple(candidates[index] for index in range(0, len(candidates), stride)[:sample_size])


def _fact_candidates(reference: Reference) -> list[RetrievalQuery]:
    queries: list[RetrievalQuery] = []
    for entity in reference.persons + reference.places + reference.objects:
        for fact in entity.facts:
            queries.append(_fact_query(entity, fact))
    return queries


def _fact_query(entity: Entity, fact: Fact) -> RetrievalQuery:
    kind: QueryKind = "state_at_time" if (fact.valid_from or fact.valid_to) else "entity_lookup"
    return RetrievalQuery(
        ref_id=fact.id,
        kind=kind,
        entity_ref=entity.id,
        entity_name=entity.name,
        predicate=fact.predicate,
        expected=fact.value,
        valid_from=fact.valid_from,
        valid_to=fact.valid_to,
    )


def _relation_candidates(reference: Reference) -> list[RetrievalQuery]:
    names = {
        entity.id: entity.name
        for entity in reference.persons + reference.places + reference.objects
    }
    queries: list[RetrievalQuery] = []
    for relation in reference.relations:
        subject = names.get(relation.subject)
        target = names.get(relation.object)
        if subject is None or target is None:
            msg = (
                f"retrieval query generation: relation {relation.id!r} endpoint not found "
                f"in reference ({relation.subject!r} / {relation.object!r})"
            )
            raise ValueError(msg)
        queries.append(
            RetrievalQuery(
                ref_id=relation.id,
                kind="relationship",
                entity_ref=relation.subject,
                entity_name=subject,
                predicate=relation.predicate,
                expected=target,
                valid_from=relation.valid_from,
                valid_to=relation.valid_to,
            )
        )
    return queries
