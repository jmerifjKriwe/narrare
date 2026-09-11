"""Retrieval scoring: reference-derived queries vs OUT records (Task 13).

Composition facade — the two halves live in their own modules (RULE-04):
query generation in ``retrieval_queries`` (deterministic strided
sampling from the reference), the per-capability coverage table in
``retrieval_coverage`` (partial-benchmarkability mapping for the run
artifacts). This module answers the generated queries against the
fetched OUT records.

Answer matching — reuse, not duplication (brief requirement 2): the T11
rules are the single source of truth and are IMPORTED verbatim —
``entity_match.match_entities`` resolves the queried entity to its
detail record, ``fact_match.score_facts`` supplies the value planes
(predicate-keyed metadata rule, boundary-aware body rule, evidence
extraction via ``actual_facts_from``), and
``relation_match.score_relations`` supplies the directed
endpoint+predicate edge matching. No matching rule is re-implemented
here.

Interval riders (Task-11 ledger, revisited in this task):

- Rider A (state_at_time): the query fact's OWN bounds are matched
  EXPLICITLY, and the answer side reads ONLY the predicate-bound
  companion keys ``{pred}_from``/``{pred}_to`` — the T11 global
  fallback to generic ``valid_from``/``valid_to`` metadata keys is
  deliberately NOT inherited (a generic key is not evidence for THIS
  query's temporal claim). The check can only DOWNGRADE a found value:
  a value-plane ``found_wrong`` stands, absent actual bounds never fail
  (the T11 tolerance), and a present-but-mismatched predicate-bound key
  fails correctness via ``normalize.boundary_matches`` (month
  precision ±1).

- Rider B (relationship): the matched edge's interval is verified IFF
  the edge ``metadata`` exposes parseable ``valid_from``/``valid_to``
  (generic keys — an edge IS single-predicate, so generic keys are
  predicate-bound by construction) and the reference relation carries
  bounds; a mismatch → ``found_wrong``. Without exposed metadata the
  relation is matched WITHOUT interval verification — the documented
  honest downgrade (``interval_checked=False``), never a fabricated
  pass.

Pure and deterministic: no clocks, no randomness (plan Global
Constraints). Aggregate conventions are documented on
``retrieval_records.RetrievalScore``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmark.corpus_views import Entity, Fact
from benchmark.drivers.out_records import EntrySummary
from benchmark.scoring.entity_match import match_entities
from benchmark.scoring.fact_match import actual_facts_from, score_facts
from benchmark.scoring.normalize import boundary_matches, normalize_predicate, parse_date_value
from benchmark.scoring.relation_match import person_genders, score_relations
from benchmark.scoring.retrieval_coverage import coverage_rows
from benchmark.scoring.retrieval_queries import DEFAULT_SAMPLE_SIZE, generate_queries
from benchmark.scoring.retrieval_records import (
    AnswerOutcome,
    AnswerStatus,
    RetrievalQuery,
    RetrievalScore,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from benchmark.corpus_views import PartialDate, Reference
    from benchmark.drivers.out_records import (
        EntityDetailRecord,
        RelationshipDetail,
        TimelineReadRecord,
    )
    from benchmark.scoring.fact_match import ActualFacts

__all__ = [
    "score_retrieval",
]


# ---------------------------------------------------------------------------
# Scoring facade
# ---------------------------------------------------------------------------


def score_retrieval(
    reference: Reference,
    details: tuple[EntityDetailRecord, ...],
    timeline: TimelineReadRecord | None = None,
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> RetrievalScore:
    """Answer the generated queries against the fetched OUT records."""
    queries = generate_queries(reference, sample_size)
    resolver = _Resolver(reference, details)
    outcomes = tuple(resolver.answer(query) for query in queries)
    found = sum(1 for outcome in outcomes if outcome.status != "missing")
    correct = sum(1 for outcome in outcomes if outcome.status == "found")
    return RetrievalScore(
        queries=queries,
        outcomes=outcomes,
        coverage=coverage_rows(details, timeline),
        answer_coverage=found / len(outcomes) if outcomes else 0.0,
        answer_precision=correct / found if found else None,
    )


class _Resolver:
    """Answers generated queries against the fetched detail records."""

    def __init__(self, reference: Reference, details: tuple[EntityDetailRecord, ...]) -> None:
        self._by_entry = {record.entry.id: record for record in details}
        expected = reference.persons + reference.places + reference.objects
        self._entity_by_id = {entity.id: entity for entity in expected}
        matched = match_entities(expected, tuple(_entry_summary(record) for record in details))
        self._detail_of_ref = {
            match.ref.id: self._by_entry[match.entry.id] for match in matched.matches
        }
        self._ref_to_entry = {match.ref.id: match.entry.id for match in matched.matches}
        self._person_gender = person_genders(reference.persons)
        self._relation_by_id = {relation.id: relation for relation in reference.relations}
        self._edges: tuple[RelationshipDetail, ...] = tuple(
            edge for record in details for edge in record.relationships
        )
        self._edges_by_id = {edge.id: edge for edge in self._edges}

    def answer(self, query: RetrievalQuery) -> AnswerOutcome:
        if query.kind == "relationship":
            return self._answer_relationship(query)
        return self._answer_fact(query)

    def _answer_fact(self, query: RetrievalQuery) -> AnswerOutcome:
        detail = self._detail_of_ref.get(query.entity_ref)
        if detail is None:
            return _outcome(query, "missing", interval_checked=False, answered_by=None)
        entity = self._entity_by_id[query.entity_ref]
        fact = self._fact_of(entity, query.ref_id)
        actual = actual_facts_from(detail.entry)
        if query.kind == "entity_lookup":
            status = score_facts(_single(entity, fact), actual)[0].status
            return _outcome(query, status, interval_checked=False, answered_by=detail.entry.id)
        return self._answer_state_at_time(query, fact, actual, detail.entry.id)

    def _answer_state_at_time(
        self,
        query: RetrievalQuery,
        fact: Fact,
        actual: ActualFacts,
        entry_id: str,
    ) -> AnswerOutcome:
        """Rider A: T11 value planes (bounds stripped) + explicit bound check."""
        value_fact = Fact(
            id=fact.id,
            predicate=fact.predicate,
            value=fact.value,
            valid_from=None,
            valid_to=None,
            source_chapters=fact.source_chapters,
        )
        value_status = score_facts(
            _single(self._entity_by_id[query.entity_ref], value_fact), actual
        )[0].status
        if value_status == "missing":
            return _outcome(query, "missing", interval_checked=False, answered_by=entry_id)
        if value_status == "found_wrong":
            return _outcome(query, "found_wrong", interval_checked=False, answered_by=entry_id)
        status, checked = _compare_bounds(
            query, lambda side: _predicate_bound(actual.metadata, fact.predicate, side)
        )
        return _outcome(query, status, interval_checked=checked, answered_by=entry_id)

    def _answer_relationship(self, query: RetrievalQuery) -> AnswerOutcome:
        relation = self._relation_by_id[query.ref_id]
        result = score_relations((relation,), self._edges, self._ref_to_entry, self._person_gender)
        matched_edge_id = result.outcomes[0].matched_edge_id
        if result.outcomes[0].status == "missing" or matched_edge_id is None:
            return _outcome(query, "missing", interval_checked=False, answered_by=None)
        edge = self._edges_by_id[matched_edge_id]
        status, checked = _edge_interval(query, edge.metadata)
        return _outcome(query, status, interval_checked=checked, answered_by=edge.id)

    def _fact_of(self, entity: Entity, ref_id: str) -> Fact:
        for fact in entity.facts:
            if fact.id == ref_id:
                return fact
        msg = f"retrieval scoring: fact {ref_id!r} not found on entity {entity.id!r}"
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# Rider checks + small helpers
# ---------------------------------------------------------------------------


def _edge_interval(
    query: RetrievalQuery, metadata: Mapping[str, object] | None
) -> tuple[AnswerStatus, bool]:
    """Rider B: verify edge intervals iff exposed; else the honest downgrade."""
    if query.valid_from is None and query.valid_to is None:
        return "found", False
    return _compare_bounds(query, lambda side: _edge_bound(metadata, side))


def _compare_bounds(
    query: RetrievalQuery, actual_bound_of: Callable[[str], PartialDate | None]
) -> tuple[AnswerStatus, bool]:
    """Shared bound comparison: absent actual bounds never fail (T11 tolerance)."""
    checked = False
    for ref_bound, side in ((query.valid_from, "from"), (query.valid_to, "to")):
        if ref_bound is None:
            continue
        actual_bound = actual_bound_of(side)
        if actual_bound is None:
            continue
        checked = True
        if not boundary_matches(ref_bound, actual_bound):
            return "found_wrong", True
    return "found", checked


def _predicate_bound(
    metadata: Mapping[str, object], predicate: str, side: str
) -> PartialDate | None:
    """Rider-A evidence plane: ONLY the predicate-bound companion key."""
    value = metadata.get(f"{normalize_predicate(predicate)}_{side}")
    return None if value is None else parse_date_value(value)


def _edge_bound(metadata: Mapping[str, object] | None, side: str) -> PartialDate | None:
    """Rider-B evidence plane: generic edge keys (an edge IS single-predicate)."""
    if metadata is None:
        return None
    value = metadata.get(f"valid_{side}")
    return None if value is None else parse_date_value(value)


def _single(entity: Entity, fact: Fact) -> Entity:
    """One-fact entity view so ``score_facts`` yields exactly the queried row."""
    return Entity(id=entity.id, name=entity.name, aliases=entity.aliases, facts=(fact,))


def _entry_summary(record: EntityDetailRecord) -> EntrySummary:
    """The identity slice ``match_entities`` resolves against."""
    entry = record.entry
    return EntrySummary(
        id=entry.id,
        name=entry.name,
        entity_type=entry.entity_type,
        slug=entry.slug,
        status=entry.status,
        review_status=entry.review_status,
    )


def _outcome(
    query: RetrievalQuery, status: AnswerStatus, *, interval_checked: bool, answered_by: str | None
) -> AnswerOutcome:
    return AnswerOutcome(
        ref_id=query.ref_id,
        kind=query.kind,
        status=status,
        interval_checked=interval_checked,
        answered_by=answered_by,
    )
