"""Fix-round-1 regressions for the fact matcher (``fact_match.py``).

Pins the two Important review findings, each with its probe evidence:

- The body rule matched at CHARACTER level (probe: fact value ``"24"``
  was found inside prose ``"gruendet 2024"``). Regression tests pin
  boundary-aware membership: whole token runs only, multi-word values
  still found, single digits never matched inside years.
- Companion interval keys (``valid_from``/``valid_to`` and
  ``{pred}_from``/``{pred}_to``) consumed as interval evidence were
  misreported as spurious facts. Regression tests pin their exemption
  from the spurious-fact predicate set, plus the negative control
  (unlicensed interval keys stay spurious).
- Temporal snapshots (scoring-diagnosis fix 1): the KB keeps the LATEST
  value under the plain key, so historical ``age_stated`` snapshots
  were scored ``found_wrong`` against it. Year-suffixed keys
  (``age_2017: 25``) now satisfy temporal facts (bounds or recurring
  snapshot predicate); non-temporal predicates ignore year keys.
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
# Body rule: boundary-aware membership (review finding 1)
# ---------------------------------------------------------------------------


def test_body_match_is_boundary_aware_not_character_level() -> None:
    """``"24"`` must NOT be found inside ``"gruendet 2024"`` (probe)."""
    outcome = score_single_fact(None, "Sie gruendet 2024 ein Buero.")
    assert outcome.status == "missing"
    assert outcome.evidence is None


def test_body_match_finds_standalone_number() -> None:
    outcome = score_single_fact(None, "Anna war 24 Jahre alt")
    assert outcome.status == "found"
    assert outcome.evidence == "body"


def test_body_match_still_finds_multi_word_phrase() -> None:
    spaced = score_single_fact(None, "Anna studiert an der HCU Hamburg.", value="HCU Hamburg")
    assert spaced.status == "found"
    assert spaced.evidence == "body"
    hyphenated = score_single_fact(None, "Anna studiert an der HCU-Hamburg.", value="HCU Hamburg")
    assert hyphenated.status == "found"
    assert hyphenated.evidence == "body"


def test_body_match_rejects_single_digit_inside_year() -> None:
    """``"2"`` must NOT be found inside ``"2024"`` (digit-in-year probe)."""
    outcome = score_single_fact(None, "Sie gruendet 2024 ein Buero.", value="2")
    assert outcome.status == "missing"
    assert outcome.evidence is None


# ---------------------------------------------------------------------------
# Spurious plane: companion interval keys are licensed (review finding 2)
# ---------------------------------------------------------------------------


def test_spurious_facts_exempt_generic_valid_interval_keys() -> None:
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact(
                        "F001",
                        "age_stated",
                        "24",
                        valid_from=d(2015),
                        valid_to=d(2017, 2),
                    ),
                ),
            ),
        ),
    )
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={"age_stated": "24", "valid_from": "2015-07", "valid_to": "2017-03"},
        ),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.spurious_facts == ()
    assert score.facts[0].status == "found"


def test_spurious_facts_exempt_predicate_companion_interval_keys() -> None:
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F001", "student_at", "HCU Hamburg", valid_to=d(2017, 2)),),
            ),
        ),
    )
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={"student_at": "HCU Hamburg", "student_at_to": "2017-02"},
        ),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.spurious_facts == ()
    assert score.facts[0].status == "found"


def test_spurious_facts_still_report_unlicensed_interval_keys() -> None:
    """Negative control: an interval key no expected fact licenses stays spurious."""
    reference = make_reference(
        persons=(ref_entity("p1", "Anna Meyer", facts=(ref_fact("F001", "age_stated", "24"),)),)
    )
    details = (
        detail("e1", name="Anna Meyer", metadata={"age_stated": 24, "employment_from": "2015"}),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert [fact.key for fact in score.spurious_facts] == ["employment_from"]


# ---------------------------------------------------------------------------
# Metadata rule: fact-key alias folding (Task 2 — predicate vocabulary)
# ---------------------------------------------------------------------------


def test_metadata_rule_folds_bare_age_key_to_reference_predicate() -> None:
    """Extraction key ``age`` must satisfy reference predicate ``age_stated``."""
    outcome = score_single_fact({"age": "24"}, None)
    assert outcome.status == "found"
    assert outcome.evidence == "metadata"


def test_metadata_rule_folds_occupation_to_profession() -> None:
    """Extraction key ``occupation`` must satisfy reference predicate ``profession``."""
    reference = make_reference(
        persons=(
            ref_entity("p1", "Lisa Brandt", facts=(ref_fact("F001", "profession", "Designerin"),)),
        ),
    )
    details = (detail("e1", name="Lisa Brandt", metadata={"occupation": "Designerin"}),)
    score = score_build_quality(reference, (summary("e1", "Lisa Brandt"),), details)
    assert score.facts[0].status == "found"
    assert score.facts[0].evidence == "metadata"


def test_metadata_rule_wrong_value_under_alias_key_is_found_wrong() -> None:
    """An alias-key hit with a differing value is a precision hit, not a miss."""
    outcome = score_single_fact({"age": "25"}, None)
    assert outcome.status == "found_wrong"
    assert outcome.evidence == "metadata"


def test_spurious_facts_licensed_through_alias_key() -> None:
    """A key folded onto an expected predicate must not be reported spurious."""
    reference = make_reference(
        persons=(ref_entity("p1", "Anna Meyer", facts=(ref_fact("F001", "age_stated", "24"),)),)
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age": "24"}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found"
    assert score.spurious_facts == ()


def test_spurious_facts_licensed_alias_companion_interval_keys() -> None:
    """Companion interval keys under the alias surface stay licensed too."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F001", "age_stated", "24", valid_from=d(2015)),),
            ),
        ),
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age": "24", "age_from": "2015-06"}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found"
    assert score.spurious_facts == ()


def test_interval_check_reads_companion_under_alias_key() -> None:
    """A contradicting interval bound under the alias surface fails correctness."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(ref_fact("F001", "age_stated", "24", valid_from=d(2015)),),
            ),
        ),
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age": "24", "age_from": "2020-01"}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found_wrong"
    assert score.facts[0].evidence == "metadata"


# ---------------------------------------------------------------------------
# Temporal metadata: year-suffixed keys (scoring-diagnosis fix 1)
# ---------------------------------------------------------------------------


def test_temporal_fact_found_via_year_suffixed_key() -> None:
    """Plain key holds the latest value; the year key satisfies the old snapshot."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact("F001", "age_stated", "24"),
                    ref_fact("F021", "age_stated", "25"),
                    ref_fact("F132", "age_stated", "35"),
                ),
            ),
        ),
    )
    details = (
        detail(
            "e1",
            name="Anna Meyer",
            metadata={"age": "35", "age_2015": "24", "age_2017": "25"},
        ),
    )
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    by_ref = {fact.ref_id: fact for fact in score.facts}
    assert by_ref["F001"].status == "found"
    assert by_ref["F021"].status == "found"
    assert by_ref["F021"].evidence == "metadata"
    assert by_ref["F132"].status == "found"
    assert score.spurious_facts == ()


def test_temporal_fact_found_via_year_key_without_plain_key() -> None:
    """A year-suffixed key alone satisfies the snapshot (no plain key present)."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact("F021", "age_stated", "25"),
                    ref_fact("F132", "age_stated", "35"),
                ),
            ),
        ),
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age_2017": "25"}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    by_ref = {fact.ref_id: fact for fact in score.facts}
    assert by_ref["F021"].status == "found"
    assert by_ref["F021"].evidence == "metadata"
    assert by_ref["F132"].status == "missing"


def test_temporal_year_key_inside_fact_bounds_is_found() -> None:
    """A bounded fact accepts the year key whose year lies in its interval."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact(
                        "F021",
                        "age_stated",
                        "25",
                        valid_from=d(2017, 2),
                        valid_to=d(2017, 12),
                    ),
                    ref_fact("F132", "age_stated", "35"),
                ),
            ),
        ),
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age": "35", "age_2017": "25"}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    by_ref = {fact.ref_id: fact for fact in score.facts}
    assert by_ref["F021"].status == "found"
    assert by_ref["F021"].evidence == "metadata"


def test_temporal_year_key_outside_fact_bounds_is_found_wrong() -> None:
    """A value-matching year key outside the fact's interval contradicts it."""
    reference = make_reference(
        persons=(
            ref_entity(
                "p1",
                "Anna Meyer",
                facts=(
                    ref_fact(
                        "F021",
                        "age_stated",
                        "25",
                        valid_from=d(2017, 2),
                        valid_to=d(2017, 12),
                    ),
                    ref_fact("F132", "age_stated", "35"),
                ),
            ),
        ),
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age_2019": "25"}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    by_ref = {fact.ref_id: fact for fact in score.facts}
    assert by_ref["F021"].status == "found_wrong"
    assert by_ref["F021"].evidence == "metadata"


def test_non_temporal_year_key_stays_spurious_and_unmatched() -> None:
    """Negative control: year keys are licensed only for time-varying predicates."""
    reference = make_reference(
        persons=(ref_entity("p1", "Anna Meyer", facts=(ref_fact("F001", "age_stated", "24"),)),)
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age": "24", "age_2017": "25"}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "found"
    assert [fact.key for fact in score.spurious_facts] == ["age_2017"]


def test_year_key_does_not_satisfy_non_temporal_fact() -> None:
    """A non-temporal fact is never satisfied by a year-suffixed key alone."""
    reference = make_reference(
        persons=(ref_entity("p1", "Anna Meyer", facts=(ref_fact("F001", "age_stated", "24"),)),)
    )
    details = (detail("e1", name="Anna Meyer", metadata={"age_2017": "24"}),)
    score = score_build_quality(reference, (summary("e1", "Anna Meyer"),), details)
    assert score.facts[0].status == "missing"
