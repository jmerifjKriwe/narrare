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
