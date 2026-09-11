"""Direction-aware matching regressions (symmetric + swapped-endpoint inverse).

Pins the two enumerated direction relaxations of the relation matcher
(measurement validity: run ``2026-09-07-clean-incremental-3`` dropped
semantically-correct kinship/colleague edges purely for orientation):

- ``SYMMETRIC_PREDICATES`` match an edge with swapped endpoints as well
  ("A colleague_of B" ≡ "B colleague_of A");
- the inverse kinship pairs (``SWAPPED_EQUIVALENCE`` after gender
  folds) match ONLY with endpoints swapped, with each gendered side's
  subject agreeing with the corpus gender — ``mother_of(A→B)`` ≡
  ``daughter_of(B→A)`` iff A female AND B female.

Strictness pins: unknown gender blocks the gendered path, endpoints
NOT swapped never trigger the inverse rules, gendered predicates never
match each other in the same direction, ``first_grandchild_of`` has no
inverse (birth order), and exact same-direction matches are unaffected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from benchmark.scoring import score_build_quality
from benchmark.tests.scoring_helpers import (
    detail,
    edge,
    make_reference,
    ref_entity,
    ref_relation,
    summary,
)

if TYPE_CHECKING:
    from benchmark.corpus_views import Gender

SYMMETRIC_PREDICATES = (
    "sibling_of",
    "spouse_of",
    "engaged_to",
    "colleague_of",
    "friend_of",
    "neighbor_of",
    "confused_in_mail_with",
    "business_partner_of",
    "unrelated_to_family_of",
)
"""Mirrors ``relation_match.SYMMETRIC_PREDICATES`` (keep in sync)."""


def _score_pair(
    reference_predicate: str,
    edge_rel_type: str,
    *,
    ref_subject_gender: Gender | None,
    object_gender: Gender | None,
    reversed_edge: bool,
) -> tuple[str, str | None]:
    """Score one p1→p2 relation against one single edge.

    ``reversed_edge=False`` yields edge e1→e2 (same direction as the
    reference), ``True`` yields e2→e1 (endpoints swapped).
    """
    reference = make_reference(
        persons=(
            ref_entity("p1", "Ilse Meyer", gender=ref_subject_gender),
            ref_entity("p2", "Anna Meyer", gender=object_gender),
        ),
        relations=(ref_relation("R001", "p1", reference_predicate, "p2"),),
    )
    entries = (summary("e1", "Ilse Meyer"), summary("e2", "Anna Meyer"))
    endpoints = ("e2", "e1") if reversed_edge else ("e1", "e2")
    details = (
        detail(
            "e1",
            name="Ilse Meyer",
            relationships=(edge("rel-1", edge_rel_type, *endpoints),),
        ),
        detail("e2", name="Anna Meyer"),
    )
    score = score_build_quality(reference, entries, details)
    return score.relations[0].status, score.relations[0].matched_edge_id


# ---------------------------------------------------------------------------
# FIX 1 — symmetric predicates match reversed edges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("predicate", SYMMETRIC_PREDICATES)
def test_symmetric_predicate_matches_reversed_edge(predicate: str) -> None:
    """Each enumerated symmetric predicate matches its swapped-endpoint edge."""
    status, matched = _score_pair(
        predicate,
        predicate,
        ref_subject_gender=None,
        object_gender=None,
        reversed_edge=True,
    )
    assert status == "found"
    assert matched == "rel-1"


@pytest.mark.parametrize("predicate", SYMMETRIC_PREDICATES)
def test_symmetric_predicate_same_direction_unaffected(predicate: str) -> None:
    """The relaxation is additive: same-direction matches keep working."""
    status, matched = _score_pair(
        predicate,
        predicate,
        ref_subject_gender=None,
        object_gender=None,
        reversed_edge=False,
    )
    assert status == "found"
    assert matched == "rel-1"


def test_asymmetric_predicates_reversed_stay_missing() -> None:
    """Non-symmetric predicates do NOT match their reversed edge."""
    for reference_predicate, edge_rel_type in (
        ("mother_of", "mother_of"),
        ("babysitter_of", "babysitter_of"),
    ):
        status, matched = _score_pair(
            reference_predicate,
            edge_rel_type,
            ref_subject_gender="female",
            object_gender="female",
            reversed_edge=True,
        )
        assert status == "missing"
        assert matched is None


def test_symmetric_match_composes_with_gender_fold() -> None:
    """``sibling_of`` ↔ reversed ``brother_of`` iff the edge subject is male.

    The fold adjudicates with each side's OWN subject: here the edge
    subject is p2 (the reference object), not the reference subject.
    """
    status, matched = _score_pair(
        "sibling_of",
        "brother_of",
        ref_subject_gender=None,
        object_gender="male",
        reversed_edge=True,
    )
    assert status == "found"
    assert matched == "rel-1"
    status, matched = _score_pair(
        "sibling_of",
        "brother_of",
        ref_subject_gender=None,
        object_gender="female",
        reversed_edge=True,
    )
    assert status == "missing"
    assert matched is None


# ---------------------------------------------------------------------------
# FIX 2 — inverse pairs match only with endpoints swapped + gender agreement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ref_predicate", "ref_gender", "edge_predicate", "edge_gender"),
    (
        ("mother_of", "female", "daughter_of", "female"),
        ("daughter_of", "female", "mother_of", "female"),
        ("father_of", "male", "daughter_of", "female"),
        ("daughter_of", "female", "father_of", "male"),
        ("mother_of", "female", "son_of", "male"),
        ("son_of", "male", "mother_of", "female"),
        ("father_of", "male", "son_of", "male"),
        ("son_of", "male", "father_of", "male"),
        ("grandmother_of", "female", "grandchild_of", None),
        ("grandchild_of", None, "grandmother_of", "female"),
        ("grandfather_of", "male", "grandchild_of", None),
        ("grandchild_of", None, "grandfather_of", "male"),
        ("parent_of", None, "child_of", None),
        ("child_of", None, "parent_of", None),
    ),
)
def test_inverse_pair_matches_with_swapped_endpoints(
    ref_predicate: str,
    ref_gender: Gender | None,
    edge_predicate: str,
    edge_gender: Gender | None,
) -> None:
    """Every enumerated inverse pair matches both ways, endpoints swapped."""
    status, matched = _score_pair(
        ref_predicate,
        edge_predicate,
        ref_subject_gender=ref_gender,
        object_gender=edge_gender,
        reversed_edge=True,
    )
    assert status == "found"
    assert matched == "rel-1"


def test_gender_mismatch_blocks_inverse_match() -> None:
    """A gendered side whose subject disagrees blocks the inverse match."""
    status, matched = _score_pair(
        "father_of",
        "daughter_of",
        ref_subject_gender="male",
        object_gender="male",
        reversed_edge=True,
    )
    assert status == "missing"
    assert matched is None
    status, matched = _score_pair(
        "mother_of",
        "son_of",
        ref_subject_gender="female",
        object_gender="female",
        reversed_edge=True,
    )
    assert status == "missing"
    assert matched is None


def test_inverse_match_stays_strict_without_known_genders() -> None:
    """Unknown gender on either gendered side keeps the pair strict."""
    cases: tuple[tuple[Gender | None, Gender | None], ...] = (
        (None, "female"),
        ("male", None),
        (None, None),
    )
    for ref_gender, object_gender in cases:
        status, matched = _score_pair(
            "father_of",
            "daughter_of",
            ref_subject_gender=ref_gender,
            object_gender=object_gender,
            reversed_edge=True,
        )
        assert status == "missing"
        assert matched is None


def test_inverse_composes_generic_ref_with_gendered_edge() -> None:
    """Generic ``parent_of`` ↔ swapped gendered ``daughter_of`` iff p2 female."""
    status, matched = _score_pair(
        "parent_of",
        "daughter_of",
        ref_subject_gender=None,
        object_gender="female",
        reversed_edge=True,
    )
    assert status == "found"
    assert matched == "rel-1"
    status, matched = _score_pair(
        "parent_of",
        "daughter_of",
        ref_subject_gender=None,
        object_gender="male",
        reversed_edge=True,
    )
    assert status == "missing"
    assert matched is None


def test_contradictory_gendered_reversal_stays_missing() -> None:
    """``daughter_of(A→B)`` vs reversed ``son_of(B→A)`` is a contradiction."""
    status, matched = _score_pair(
        "daughter_of",
        "son_of",
        ref_subject_gender="female",
        object_gender="male",
        reversed_edge=True,
    )
    assert status == "missing"
    assert matched is None


def test_no_inverse_match_without_endpoint_swap() -> None:
    """Same-direction gendered pair is NOT equivalent (no fold to generic)."""
    status, matched = _score_pair(
        "mother_of",
        "daughter_of",
        ref_subject_gender="female",
        object_gender="female",
        reversed_edge=False,
    )
    assert status == "missing"
    assert matched is None


def test_first_grandchild_has_no_inverse_or_symmetric_match() -> None:
    """Birth order has no inverse: ``first_grandchild_of`` stays strict."""
    cases: tuple[tuple[str, str, Gender | None], ...] = (
        ("first_grandchild_of", "first_grandchild_of", None),
        ("grandmother_of", "first_grandchild_of", "female"),
        ("first_grandchild_of", "grandmother_of", None),
    )
    for ref_predicate, edge_predicate, ref_gender in cases:
        status, matched = _score_pair(
            ref_predicate,
            edge_predicate,
            ref_subject_gender=ref_gender,
            object_gender=None,
            reversed_edge=True,
        )
        assert status == "missing"
        assert matched is None


def test_exact_same_direction_match_unaffected() -> None:
    """Regression anchor: exact same-direction matching is untouched."""
    status, matched = _score_pair(
        "father_of",
        "father_of",
        ref_subject_gender="male",
        object_gender="female",
        reversed_edge=False,
    )
    assert status == "found"
    assert matched == "rel-1"
