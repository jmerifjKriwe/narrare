"""Unit tests for the KB build-quality scorer (Task 11).

Synthetic reference vs synthetic KB records (fixtures in
``scoring_helpers.py``): entity matching (exact/normalized/alias/
missing/spurious), fact scoring (metadata rule, body-substring rule,
wrong-value precision hits, month-precision interval tolerance),
relation scoring via the entity resolution map, aggregate
coverage/precision math, and reference-id traceability.
"""

from __future__ import annotations

from benchmark.corpus_views import PartialDate
from benchmark.scoring import (
    BuildQualityScore,
    score_build_quality,
)
from benchmark.scoring.normalize import normalize_predicate, normalize_text, parse_date_value
from benchmark.tests.scoring_helpers import (
    d,
    detail,
    edge,
    make_reference,
    ref_entity,
    ref_fact,
    ref_relation,
    summary,
)

# ---------------------------------------------------------------------------
# Normalization primitives
# ---------------------------------------------------------------------------


def test_normalize_text_folds_case_whitespace_and_punctuation() -> None:
    assert normalize_text("  Anna   MEYER ") == "anna meyer"
    assert normalize_text("Anna-Meyer") == "anna meyer"
    assert normalize_text("Anna  Meyer") == normalize_text("anna meyer")


def test_normalize_predicate_is_snake_case() -> None:
    assert normalize_predicate("Sibling  Of") == "sibling_of"
    assert normalize_predicate("sibling_of") == normalize_predicate("Sibling_Of")


def test_parse_date_value_accepts_year_month_day_strings_and_int_years() -> None:
    assert parse_date_value("2017-02") == PartialDate(year=2017, month=2)
    assert parse_date_value("2019-06-08") == PartialDate(year=2019, month=6, day=8)
    assert parse_date_value(1983) == PartialDate(year=1983)
    assert parse_date_value("Februar") is None


# ---------------------------------------------------------------------------
# Entity matching (through the public scorer)
# ---------------------------------------------------------------------------


def test_entity_exact_name_match() -> None:
    score = score_build_quality(
        make_reference(persons=(ref_entity("p1", "Anna Meyer"),)),
        entries=(summary("e1", "Anna Meyer"),),
        details=(detail("e1", name="Anna Meyer"),),
    )
    assert score.entities[0].status == "found"
    assert score.entities[0].matched_entry_id == "e1"
    assert score.entities[0].matched_via == "name"


def test_entity_name_normalized_match_case_and_whitespace() -> None:
    score = score_build_quality(
        make_reference(persons=(ref_entity("p1", "Anna Meyer"),)),
        entries=(summary("e1", "anna   MEYER"),),
        details=(),
    )
    assert score.entities[0].status == "found"
    assert score.entities[0].matched_via == "name"


def test_entity_slug_match_when_entry_name_differs() -> None:
    score = score_build_quality(
        make_reference(persons=(ref_entity("p1", "Anna Meyer"),)),
        entries=(summary("e1", "A. Meyer", slug="anna-meyer"),),
        details=(),
    )
    assert score.entities[0].status == "found"
    assert score.entities[0].matched_via == "slug"


def test_entity_alias_match_prevents_spurious_classification() -> None:
    score = score_build_quality(
        make_reference(persons=(ref_entity("p1", "Alexander Wolf", aliases=("Alex", "Sascha")),)),
        entries=(summary("e1", "Alex"),),
        details=(),
    )
    assert score.entities[0].status == "found"
    assert score.entities[0].matched_via == "alias:Alex"
    assert score.spurious_entities == ()


def test_entity_missing_when_no_entry_matches() -> None:
    score = score_build_quality(
        make_reference(
            persons=(ref_entity("p1", "Anna Meyer", facts=(ref_fact("F1", "age", "24"),)),)
        ),
        entries=(),
        details=(),
    )
    assert score.entities[0].status == "missing"
    assert score.entities[0].matched_entry_id is None


def test_spurious_entity_itemized_with_entry_identity() -> None:
    score = score_build_quality(
        make_reference(persons=(ref_entity("p1", "Anna Meyer"),)),
        entries=(summary("e1", "Anna Meyer"), summary("e2", "Der Erzaehler")),
        details=(detail("e1", name="Anna Meyer"),),
    )
    assert len(score.spurious_entities) == 1
    assert score.spurious_entities[0].entry_id == "e2"
    assert score.spurious_entities[0].name == "Der Erzaehler"


# ---------------------------------------------------------------------------
# Fact scoring (through the public scorer)
# ---------------------------------------------------------------------------


def score_single_fact(
    metadata: dict[str, object] | None,
    body: str | None,
    *,
    valid_from: PartialDate | None = None,
    valid_to: PartialDate | None = None,
):
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact("F001", "age_stated", "24", valid_from=valid_from, valid_to=valid_to),
                ),
            ),
        ),
    )
    entries = (summary("e1", "Anna Meyer"),)
    details = (detail("e1", name="Anna Meyer", metadata=metadata, body=body),)
    return score_build_quality(reference, entries, details).facts[0]


def test_fact_found_via_metadata_value() -> None:
    outcome = score_single_fact({"age_stated": 24}, None)
    assert outcome.status == "found"
    assert outcome.evidence == "metadata"


def test_fact_found_via_body_substring() -> None:
    outcome = score_single_fact(None, "Anna ist 24 Jahre alt.")
    assert outcome.status == "found"
    assert outcome.evidence == "body"


def test_fact_wrong_value_via_metadata_is_precision_hit() -> None:
    outcome = score_single_fact({"age_stated": "27"}, None)
    assert outcome.status == "found_wrong"
    assert outcome.evidence == "metadata"


def test_fact_missing_without_any_evidence() -> None:
    outcome = score_single_fact(None, None)
    assert outcome.status == "missing"
    assert outcome.evidence is None


def test_interval_boundary_tolerance_at_month_precision() -> None:
    within = score_single_fact(
        {"age_stated": "24", "valid_to": "2017-03"}, None, valid_to=d(2017, 2)
    )
    assert within.status == "found"
    beyond = score_single_fact(
        {"age_stated": "24", "valid_to": "2017-05"}, None, valid_to=d(2017, 2)
    )
    assert beyond.status == "found_wrong"


def test_interval_year_precision_reference_tolerates_any_month() -> None:
    outcome = score_single_fact(
        {"age_stated": "24", "valid_from": "2015-07"}, None, valid_from=d(2015)
    )
    assert outcome.status == "found"


def test_interval_absent_actual_dates_never_fail() -> None:
    outcome = score_single_fact({"age_stated": "24"}, None, valid_to=d(2017, 2))
    assert outcome.status == "found"


def test_spurious_metadata_fact_itemized_with_key_and_value() -> None:
    reference = make_reference(
        persons=(ref_entity("p1", "Anna Meyer", facts=(ref_fact("F001", "age_stated", "24"),)),)
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age_stated": 24, "importance": "high"}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert len(score.spurious_facts) == 1
    assert score.spurious_facts[0].entry_id == "e1"
    assert score.spurious_facts[0].key == "importance"
    assert score.spurious_facts[0].value == "high"


# ---------------------------------------------------------------------------
# Relation scoring (through the public scorer)
# ---------------------------------------------------------------------------


def test_relation_match_via_resolution_map() -> None:
    reference = make_reference(
        persons=(ref_entity("p1", "Anna Meyer"), ref_entity("p2", "Ben Schulz")),
        relations=(ref_relation("R001", "p1", "sibling_of", "p2"),),
    )
    entries = (summary("e1", "Anna Meyer"), summary("e2", "Ben Schulz"))
    details = (
        detail("e1", name="Anna Meyer", relationships=(edge("rel-1", "sibling_of", "e1", "e2"),)),
        detail("e2", name="Ben Schulz"),
    )
    score = score_build_quality(reference, entries, details)
    assert score.relations[0].status == "found"
    assert score.relations[0].matched_edge_id == "rel-1"


def test_relation_missing_when_endpoint_unresolved() -> None:
    reference = make_reference(
        persons=(ref_entity("p1", "Anna Meyer"), ref_entity("p2", "Ben Schulz")),
        relations=(ref_relation("R001", "p1", "sibling_of", "p2"),),
    )
    entries = (summary("e1", "Anna Meyer"),)  # p2 has no KB entry
    details = (detail("e1", name="Anna Meyer"),)
    score = score_build_quality(reference, entries, details)
    assert score.relations[0].status == "missing"
    assert score.relations[0].matched_edge_id is None


def test_relation_missing_on_predicate_mismatch() -> None:
    reference = make_reference(
        persons=(ref_entity("p1", "Anna Meyer"), ref_entity("p2", "Ben Schulz")),
        relations=(ref_relation("R001", "p1", "sibling_of", "p2"),),
    )
    entries = (summary("e1", "Anna Meyer"), summary("e2", "Ben Schulz"))
    details = (
        detail("e1", name="Anna Meyer", relationships=(edge("rel-1", "brother_of", "e1", "e2"),)),
        detail("e2", name="Ben Schulz"),
    )
    score = score_build_quality(reference, entries, details)
    assert score.relations[0].status == "missing"


def test_spurious_relation_itemized_with_edge_identity() -> None:
    reference = make_reference(persons=(ref_entity("p1", "Anna Meyer"),))
    entries = (summary("e1", "Anna Meyer"),)
    details = (
        detail("e1", name="Anna Meyer", relationships=(edge("rel-9", "lives_in", "e1", "e1"),)),
    )
    score = score_build_quality(reference, entries, details)
    assert len(score.spurious_relations) == 1
    assert score.spurious_relations[0].edge_id == "rel-9"
    assert score.spurious_relations[0].rel_type == "lives_in"


# ---------------------------------------------------------------------------
# Aggregates, traceability, determinism
# ---------------------------------------------------------------------------


def end_to_end_score() -> BuildQualityScore:
    """Reference with 3 entities / 2 facts / 1 relation vs a KB that misses one entity."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact("F004", "age_stated", "24"),
                    ref_fact(
                        "F005",
                        "student_at",
                        "HCU Hamburg",
                        valid_to=PartialDate(year=2017, month=2),
                    ),
                ),
            ),
            ref_entity("p2", "Ben Schulz"),
        ),
        places=(ref_entity("pl1", "Pfeiffer & Partner"),),
        relations=(ref_relation("R001", "p1", "sibling_of", "p2"),),
    )
    entries = (summary("e1", "Anna Meyer"), summary("e2", "Ben Schulz"), summary("e3", "Zwerg"))
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={"age_stated": 24, "importance": "high"},
            body="Anna studiert an der HCU Hamburg bis Februar 2017.",
            relationships=(
                edge("rel-1", "sibling_of", "e1", "e2"),
                edge("rel-2", "lives_in", "e2", "e3"),
            ),
        ),
        detail("e2", name="Ben Schulz"),
    )
    return score_build_quality(reference, entries, details)


def test_aggregate_coverage_and_precision_math() -> None:
    score = end_to_end_score()
    assert score.entity_coverage == 2 / 3  # p1, p2 found; pl1 missing
    assert score.fact_coverage == 1.0  # F004 metadata + F005 body
    assert score.fact_precision == 1.0
    assert score.relation_coverage == 1.0
    assert len(score.entities) == 3
    assert len(score.facts) == 2
    assert len(score.relations) == 1


def test_spurious_lists_carry_actual_identities() -> None:
    score = end_to_end_score()
    assert [entity.entry_id for entity in score.spurious_entities] == ["e3"]
    assert [fact.key for fact in score.spurious_facts] == ["importance"]
    assert [relation.edge_id for relation in score.spurious_relations] == ["rel-2"]


def test_itemizations_carry_reference_ids_for_traceability() -> None:
    score = end_to_end_score()
    assert [entity.ref_id for entity in score.entities] == ["p1", "p2", "pl1"]
    assert [fact.ref_id for fact in score.facts] == ["F004", "F005"]
    assert score.facts[0].entity_ref_id == "p1"
    assert score.relations[0].ref_id == "R001"
    assert score.relations[0].subject == "p1"
    assert score.relations[0].object == "p2"


def test_precision_is_none_when_nothing_was_found() -> None:
    score = score_build_quality(
        make_reference(
            persons=(ref_entity("p1", "Anna Meyer", facts=(ref_fact("F1", "age", "24"),)),)
        ),
        entries=(),
        details=(),
    )
    assert score.entity_coverage == 0.0
    assert score.fact_coverage == 0.0
    assert score.fact_precision is None
    assert score.relation_coverage == 0.0


def test_scorer_is_deterministic_for_identical_inputs() -> None:
    assert end_to_end_score() == end_to_end_score()
