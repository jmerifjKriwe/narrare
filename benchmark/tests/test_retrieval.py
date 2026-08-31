"""Retrieval scoring tests (Task 13): queries, matching, riders, coverage.

TDD RED state: this module was written BEFORE its implementation existed
(``benchmark/scoring/retrieval*.py``); first collection fails with
``ModuleNotFoundError`` (documented in the task report). Coverage:
generation determinism + strided selection, per-kind answer matching
(T11 rule reuse), rider-A explicit intervals (no global fallback),
rider-B relationship interval metadata (honest downgrade), the partial
surface table, and the coverage rows for the artifacts table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from benchmark.scoring import score_retrieval
from benchmark.scoring.retrieval_queries import generate_queries
from benchmark.tests.retrieval_helpers import (
    d,
    detail,
    edge_meta,
    empty_timeline,
    expected_outcome,
    ref_relation_interval,
    reference,
    retrieve,
)
from benchmark.tests.scoring_helpers import (
    Reference,
    make_reference,
    ref_entity,
    ref_fact,
    ref_relation,
)

if TYPE_CHECKING:
    from benchmark.drivers.out_records import EntityDetailRecord

# ---------------------------------------------------------------------------
# Query generation: determinism, kinds, strided selection, guards
# ---------------------------------------------------------------------------


def test_generation_and_scoring_are_deterministic() -> None:
    details = (detail("e1", name="Anna Meyer", metadata={"age_stated": 24}),)
    assert retrieve(details) == retrieve(details)
    assert generate_queries(reference()) == generate_queries(reference())


def test_query_kinds_split_by_interval_presence() -> None:
    queries = generate_queries(reference())
    assert [(query.ref_id, query.kind) for query in queries] == [
        ("F001", "entity_lookup"),
        ("F002", "state_at_time"),
        ("F003", "state_at_time"),
        ("OF001", "entity_lookup"),
        ("R001", "relationship"),
    ]
    by_id = {query.ref_id: query for query in queries}
    assert by_id["F001"].entity_name == "Anna Meyer"
    assert by_id["F001"].expected == "24"
    assert by_id["F002"].valid_from == d(2017, 3)
    assert by_id["F002"].valid_to == d(2021, 8)
    assert by_id["R001"].entity_name == "Anna Meyer"
    assert by_id["R001"].expected == "Ben Schulz"
    assert by_id["R001"].predicate == "sibling_of"


def test_strided_selection_is_stable_and_capped() -> None:
    facts = tuple(ref_fact(f"F{i:02d}", "age_stated", str(20 + i)) for i in range(1, 17))
    persons = tuple(
        ref_entity(f"p{i}", f"Person {i}", facts=facts[(i - 1) * 4 : i * 4]) for i in range(1, 5)
    )
    queries = generate_queries(make_reference(persons=persons), sample_size=5)
    assert [query.ref_id for query in queries] == ["F01", "F04", "F07", "F10", "F13"]


def test_sample_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="sample_size"):
        generate_queries(reference(), sample_size=0)


def test_unresolvable_relation_endpoint_is_a_hard_error() -> None:
    broken = make_reference(
        persons=(ref_entity("p1", "Anna Meyer"),),
        relations=(ref_relation("R001", "p1", "sibling_of", "p_ghost"),),
    )
    with pytest.raises(ValueError, match="p_ghost"):
        score_retrieval(broken, (), None)


# ---------------------------------------------------------------------------
# Answer matching per kind (T11 rule reuse)
# ---------------------------------------------------------------------------


def test_entity_lookup_found_via_metadata() -> None:
    score = retrieve((detail("e1", name="Anna Meyer", metadata={"age_stated": 24}),))
    outcome = expected_outcome(score, "F001")
    assert outcome.status == "found"
    assert outcome.answered_by == "e1"
    assert outcome.interval_checked is False


def test_entity_lookup_body_rule_is_boundary_aware() -> None:
    found = retrieve((detail("e1", name="Anna Meyer", body="Anna war 24 Jahre alt."),))
    assert expected_outcome(found, "F001").status == "found"
    inside_year = retrieve((detail("e1", name="Anna Meyer", body="Sie gruendet 2024 ein Buero."),))
    assert expected_outcome(inside_year, "F001").status == "missing"


def test_query_without_detail_record_is_missing() -> None:
    score = retrieve(())
    outcome = expected_outcome(score, "F001")
    assert outcome.status == "missing"
    assert outcome.answered_by is None


def test_state_at_time_wrong_value_is_found_wrong() -> None:
    score = retrieve((detail("e1", name="Anna Meyer", metadata={"profession": "Studentin"}),))
    assert expected_outcome(score, "F002").status == "found_wrong"


def test_state_at_time_interval_uses_predicate_bound_keys() -> None:
    consistent = retrieve(
        (
            detail(
                "e1",
                name="Anna Meyer",
                metadata={
                    "profession": "Projektarchitektin",
                    "profession_from": "2017-04",
                    "profession_to": "2021-08",
                },
            ),
        )
    )
    outcome = expected_outcome(consistent, "F002")
    assert outcome.status == "found"
    assert outcome.interval_checked is True
    contradicted = retrieve(
        (
            detail(
                "e1",
                name="Anna Meyer",
                metadata={"profession": "Projektarchitektin", "profession_from": "2018-01"},
            ),
        )
    )
    assert expected_outcome(contradicted, "F002").status == "found_wrong"


def test_state_at_time_generic_interval_keys_are_not_evidence() -> None:
    """Rider A: the generic valid_from fallback must NOT verify the interval."""
    score = retrieve(
        (
            detail(
                "e1",
                name="Anna Meyer",
                metadata={"profession": "Projektarchitektin", "valid_from": "2014-01"},
            ),
        )
    )
    outcome = expected_outcome(score, "F002")
    assert outcome.status == "found"
    assert outcome.interval_checked is False


def test_relationship_found_via_resolved_edge() -> None:
    details = (
        detail("e1", name="Anna Meyer"),
        detail(
            "e2",
            name="Ben Schulz",
            relationships=(edge_meta("rel-1", "sibling_of", "e1", "e2"),),
        ),
    )
    outcome = expected_outcome(retrieve(details), "R001")
    assert outcome.status == "found"
    assert outcome.answered_by == "rel-1"


def test_relationship_missing_without_edge_or_endpoint() -> None:
    score = retrieve((detail("e1", name="Anna Meyer"),))
    outcome = expected_outcome(score, "R001")
    assert outcome.status == "missing"
    assert outcome.answered_by is None


# ---------------------------------------------------------------------------
# Rider B: relationship interval metadata (honest downgrade)
# ---------------------------------------------------------------------------


def interval_reference() -> Reference:
    return make_reference(
        persons=(ref_entity("p1", "Anna Meyer"), ref_entity("p2", "Ben Schulz")),
        relations=(
            ref_relation_interval(
                "R001", "p1", "sibling_of", "p2", valid_from=d(2017, 3), valid_to=d(2021, 8)
            ),
        ),
    )


def ben_with_edge(metadata: dict[str, object] | None) -> tuple[EntityDetailRecord, ...]:
    return (
        detail("e1", name="Anna Meyer"),
        detail(
            "e2",
            name="Ben Schulz",
            relationships=(edge_meta("rel-1", "sibling_of", "e1", "e2", metadata=metadata),),
        ),
    )


def test_relationship_interval_metadata_is_checked_when_exposed() -> None:
    consistent = score_retrieval(
        interval_reference(), ben_with_edge({"valid_from": "2017-03", "valid_to": "2021-08"}), None
    )
    outcome = expected_outcome(consistent, "R001")
    assert outcome.status == "found"
    assert outcome.interval_checked is True
    contradicted = score_retrieval(
        interval_reference(), ben_with_edge({"valid_from": "2018-01"}), None
    )
    assert expected_outcome(contradicted, "R001").status == "found_wrong"


def test_relationship_without_exposed_intervals_downgrades_honestly() -> None:
    score = score_retrieval(interval_reference(), ben_with_edge(None), None)
    outcome = expected_outcome(score, "R001")
    assert outcome.status == "found"
    assert outcome.interval_checked is False


# ---------------------------------------------------------------------------
# Partial surface table + coverage rows + aggregates
# ---------------------------------------------------------------------------


def test_partial_surface_table_documents_inventory_verdicts() -> None:
    rows = {row.capability: row for row in retrieve(()).coverage}
    assert len(rows) == 10
    assert rows["CAP-OUT-03"].surface == "scored"
    assert rows["CAP-OUT-06"].surface == "recorded"
    assert "LLM judge" in rows["CAP-OUT-06"].reason
    assert "recorded-not-scored" in rows["CAP-OUT-06"].reason
    assert rows["CAP-OUT-05"].surface == "skipped"
    assert "no series" in rows["CAP-OUT-05"].reason
    assert rows["CAP-OUT-10"].surface == "recorded"
    assert "template reads driven" in rows["CAP-OUT-10"].reason
    assert "v1 query set samples entity facts/relations only" in rows["CAP-OUT-02"].reason
    assert rows["CAP-OUT-07"].surface == "recorded"


def test_coverage_rows_carry_driven_flags_from_supplied_records() -> None:
    driven = {
        row.capability: row
        for row in retrieve((detail("e1", name="Anna Meyer"),), empty_timeline()).coverage
    }
    assert driven["CAP-OUT-03"].driven is True
    assert driven["CAP-OUT-07"].driven is True
    undriven = {
        row.capability: row for row in retrieve((detail("e1", name="Anna Meyer"),)).coverage
    }
    assert undriven["CAP-OUT-07"].driven is False
    assert undriven["CAP-OUT-03"].driven is True
    assert all(
        row.driven is False
        for row in retrieve(()).coverage
        if row.capability not in {"CAP-OUT-03", "CAP-OUT-07"}
    )


def test_timeline_record_is_recorded_not_matched() -> None:
    without = retrieve((detail("e1", name="Anna Meyer"),))
    with_timeline = retrieve((detail("e1", name="Anna Meyer"),), empty_timeline())
    assert with_timeline.outcomes == without.outcomes
    rows = {row.capability: row for row in with_timeline.coverage}
    assert rows["CAP-OUT-07"].driven is True


def test_aggregate_conventions_match_build_quality() -> None:
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={"age_stated": 24, "profession": "Studentin"},
        ),
        detail(
            "e2",
            name="Ben Schulz",
            relationships=(edge_meta("rel-1", "sibling_of", "e1", "e2"),),
        ),
    )
    score = retrieve(details)
    assert score.answer_coverage == 3 / 5  # F001 found, F002 found_wrong, R001 found
    assert score.answer_precision == 2 / 3
    empty = retrieve(())
    assert empty.answer_coverage == 0.0
    assert empty.answer_precision is None
