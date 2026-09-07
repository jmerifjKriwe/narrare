"""Fact-match measurement-validity regressions (fix round 2).

Run ``2026-09-07-clean-incremental-1`` measured fact precision at 37% (29
``found_wrong``) although the KB substantively captured the knowledge.
Three matcher gaps, each pinned here with the run's real data shapes:

- **Temporal key grammar**: the extraction writes ``age_2019_12``
  (year_month) and ``profession_2016_2021`` (year range); the matcher
  only accepted ``pred_YYYY``. A temporal key matches when its year set
  covers the fact's anchor year; out-of-coverage value matches stay
  ``found_wrong`` contradictions.
- **Value equality**: the reference states "Projektarchitektin bei
  Pfeiffer & Partner Architekten" while the KB splits it into
  ``profession_2016_2021`` = "Projektarchitektin (HafenCity, Hamburg)"
  plus a companion employer key. Reference core tokens (stopwords
  stripped) must ALL appear across the candidate value plus companion
  values — no partial credit; numeric references keep exact matching.
- **Inverse residence**: reference ``residence_of`` facts live on PLACE
  entities with entity-id values, while the binding is stated on the
  person entry's ``residence`` key — the inverse path is valid evidence.
"""

from __future__ import annotations

from benchmark.scoring import score_build_quality
from benchmark.tests.scoring_helpers import (
    d,
    detail,
    make_reference,
    ref_entity,
    ref_fact,
    score_single_fact,
    summary,
)

# ---------------------------------------------------------------------------
# FIX 1: temporal key variants — year_month form (`age_2019_12`)
# ---------------------------------------------------------------------------


def test_year_month_key_matches_fact_anchored_in_same_year() -> None:
    """``age_2019_12`` covers a reference fact anchored at 2019."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F001", "age_stated", "29", valid_from=d(2019)),),
            ),
        ),
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age_2019_12": 29}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found"
    assert score.facts[0].evidence == "metadata"
    assert score.spurious_facts == ()


def test_year_month_key_outside_anchor_year_is_found_wrong() -> None:
    """``age_2019_12`` does NOT cover a fact anchored at 2020 — contradiction."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F001", "age_stated", "29", valid_from=d(2020)),),
            ),
        ),
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age_2019_12": 29}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found_wrong"
    assert score.facts[0].evidence == "metadata"


# ---------------------------------------------------------------------------
# FIX 1: temporal key variants — year range form (`profession_2016_2021`)
# ---------------------------------------------------------------------------


def test_year_range_key_covers_anchor_years_inside_range() -> None:
    """``profession_2016_2021`` covers anchors 2017 and 2021 (real F022 shape)."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact("F001", "profession", "Projektarchitektin", valid_from=d(2017, 3)),
                    ref_fact("F002", "profession", "Projektarchitektin", valid_from=d(2021)),
                ),
            ),
        ),
    )
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={"profession_2016_2021": "Projektarchitektin (HafenCity, Hamburg)"},
        ),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    by_ref = {fact.ref_id: fact for fact in score.facts}
    assert by_ref["F001"].status == "found"
    assert by_ref["F002"].status == "found"
    assert score.spurious_facts == ()


def test_year_range_key_before_range_start_is_found_wrong() -> None:
    """``profession_2016_2021`` does NOT cover an anchor at 2015."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F001", "profession", "Projektarchitektin", valid_from=d(2015)),),
            ),
        ),
    )
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={"profession_2016_2021": "Projektarchitektin (HafenCity, Hamburg)"},
        ),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found_wrong"
    assert score.facts[0].evidence == "metadata"


# ---------------------------------------------------------------------------
# FIX 2: semantic text-value matching with companion keys
# ---------------------------------------------------------------------------


def test_semantic_value_match_via_workplace_companion_key() -> None:
    """Reference phrasing + range key + real companion key (run data, F022)."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact(
                        "F022",
                        "profession",
                        "Projektarchitektin bei Pfeiffer & Partner Architekten",
                        valid_from=d(2017, 3),
                        valid_to=d(2021, 8),
                    ),
                ),
            ),
        ),
    )
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={
                "profession_2016_2021": "Projektarchitektin (HafenCity, Hamburg)",
                "workplace": "Pfeiffer & Partner Architekten (seit März 2017)",
            },
        ),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found"
    assert score.facts[0].evidence == "metadata"
    assert score.spurious_facts == ()


def test_semantic_value_match_via_employer_companion_key() -> None:
    """Plain key path: employer companion completes the reference tokens."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F022", "profession", "Projektarchitektin bei Pfeiffer"),),
            ),
        ),
    )
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={
                "profession": "Projektarchitektin (HafenCity, Hamburg)",
                "employer": "Pfeiffer",
            },
        ),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found"
    assert score.facts[0].evidence == "metadata"
    assert score.spurious_facts == ()


def test_semantic_value_missing_tokens_without_companion_is_missing() -> None:
    """No partial credit: temporal candidate without companion cannot satisfy."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact(
                        "F022",
                        "profession",
                        "Projektarchitektin bei Pfeiffer & Partner Architekten",
                        valid_from=d(2017, 3),
                        valid_to=d(2021, 8),
                    ),
                ),
            ),
        ),
    )
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={"profession_2016_2021": "Projektarchitektin (HafenCity, Hamburg)"},
        ),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "missing"
    assert score.facts[0].evidence is None


def test_semantic_value_missing_tokens_under_plain_key_is_found_wrong() -> None:
    """Plain key with unsubstantive value stays a precision hit (no rescue)."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F022", "profession", "Projektarchitektin bei Pfeiffer"),),
            ),
        ),
    )
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={"profession": "Projektarchitektin (HafenCity, Hamburg)"},
        ),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found_wrong"
    assert score.facts[0].evidence == "metadata"


def test_companion_value_key_is_not_reported_spurious() -> None:
    """A consumed companion key is licensed evidence, not spurious structure."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F022", "profession", "Architektin"),),
            ),
        ),
    )
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={"profession": "Architektin", "workplace": "Pfeiffer & Partner"},
        ),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found"
    assert score.spurious_facts == ()


# ---------------------------------------------------------------------------
# FIX 2: numeric exactness is preserved
# ---------------------------------------------------------------------------


def test_numeric_exactness_preserved() -> None:
    """29 vs 30 stays wrong — semantic relaxation never applies to numbers."""
    outcome = score_single_fact({"age_stated": "30"}, None, value="29")
    assert outcome.status == "found_wrong"
    assert outcome.evidence == "metadata"


def test_numeric_value_stays_exact_against_phrase_candidate() -> None:
    """A numeric reference does not subset-match a richer phrase candidate."""
    outcome = score_single_fact({"age_stated": "29 Jahre"}, None, value="29")
    assert outcome.status == "found_wrong"
    assert outcome.evidence == "metadata"


# ---------------------------------------------------------------------------
# FIX 3: inverse residence path (`residence_of` on the place entity)
# ---------------------------------------------------------------------------


def test_residence_of_found_via_inverse_person_residence_key() -> None:
    """Place fact ``residence_of: p1`` is satisfied by the person's residence."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F006", "residence", "Eppendorfer Baum 14", valid_from=d(2015)),),
            ),
        ),
        places=(
            ref_entity(
                "pl1",
                "Eppendorfer Baum 14",
                facts=(ref_fact("PF001", "residence_of", "p1", valid_from=d(2015)),),
            ),
        ),
    )
    entries = (
        summary("e-p", "Anna Meyer"),
        summary("e-l", "Eppendorfer Baum 14", entity_type="location"),
    )
    details = (
        detail(
            "e-p", name="Anna Meyer", metadata={"residence_2019": "Eppendorfer Baum 14, Hamburg"}
        ),
        detail("e-l", name="Eppendorfer Baum 14", entity_type="location"),
    )
    score = score_build_quality(reference, entries, details)
    by_ref = {fact.ref_id: fact for fact in score.facts}
    assert by_ref["F006"].status == "found"
    assert by_ref["PF001"].status == "found"
    assert by_ref["PF001"].evidence == "metadata"
    assert score.spurious_facts == ()


def test_residence_of_stays_missing_when_inverse_evidence_absent() -> None:
    """Negative control: no place name in any person residence key → missing."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F006", "residence", "Türkenstraße 41", valid_from=d(2021, 8)),),
            ),
        ),
        places=(
            ref_entity(
                "pl1",
                "Eppendorfer Baum 14",
                facts=(ref_fact("PF001", "residence_of", "p1", valid_from=d(2015)),),
            ),
        ),
    )
    entries = (
        summary("e-p", "Anna Meyer"),
        summary("e-l", "Eppendorfer Baum 14", entity_type="location"),
    )
    details = (
        detail("e-p", name="Anna Meyer", metadata={"residence_2019": "Türkenstraße 41, München"}),
        detail("e-l", name="Eppendorfer Baum 14", entity_type="location"),
    )
    score = score_build_quality(reference, entries, details)
    by_ref = {fact.ref_id: fact for fact in score.facts}
    assert by_ref["PF001"].status == "missing"
    assert by_ref["PF001"].evidence is None
