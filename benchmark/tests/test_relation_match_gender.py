"""Gender-aware kinship equivalence regressions (relation scorer).

Pins the enumerated ``GENDER_EQUIVALENCE`` table: a generic kinship
predicate matches its gendered counterpart only when the shared
subject's corpus gender agrees with the gendered side (measurement
validity: run 2026-09-07-clean-incremental-2 R014, where the KB edge
``parent_of`` Peter→Juna was counted spurious+missing against reference
``father_of``). Unknown gender stays strict, two gendered predicates
are never equivalent, and ``grandchild_of`` vs ``first_grandchild_of``
is deliberately not a gender pair.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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


def _score(
    reference_predicate: str,
    edge_rel_type: str,
    *,
    subject_gender: Gender | None,
) -> tuple[str, str | None]:
    """Score one relation against one single-edge KB (subject = p1)."""
    reference = make_reference(
        persons=(
            ref_entity("p1", "Peter Meyer", gender=subject_gender),
            ref_entity("p2", "Juna Meyer"),
        ),
        relations=(ref_relation("R001", "p1", reference_predicate, "p2"),),
    )
    entries = (summary("e1", "Peter Meyer"), summary("e2", "Juna Meyer"))
    details = (
        detail(
            "e1",
            name="Peter Meyer",
            relationships=(edge("rel-1", edge_rel_type, "e1", "e2"),),
        ),
        detail("e2", name="Juna Meyer"),
    )
    score = score_build_quality(reference, entries, details)
    return score.relations[0].status, score.relations[0].matched_edge_id


def test_gendered_ref_matches_generic_kb_edge_for_male_subject() -> None:
    """Reference ``father_of`` ↔ KB edge ``parent_of`` iff subject male (R014)."""
    status, matched = _score("father_of", "parent_of", subject_gender="male")
    assert status == "found"
    assert matched == "rel-1"


def test_generic_ref_matches_gendered_kb_edge_for_male_subject() -> None:
    """Both directions: reference ``parent_of`` ↔ KB edge ``father_of``."""
    status, matched = _score("parent_of", "father_of", subject_gender="male")
    assert status == "found"
    assert matched == "rel-1"


def test_equivalence_stays_strict_without_known_gender() -> None:
    """Unknown subject gender → no equivalence match (strict fallback)."""
    status, matched = _score("father_of", "parent_of", subject_gender=None)
    assert status == "missing"
    assert matched is None


def test_mother_side_requires_female_subject() -> None:
    """``parent_of`` ↔ ``mother_of`` matches for a female subject only."""
    status, matched = _score("mother_of", "parent_of", subject_gender="female")
    assert status == "found"
    assert matched == "rel-1"
    status, matched = _score("mother_of", "parent_of", subject_gender="male")
    assert status == "missing"
    assert matched is None


def test_gendered_predicates_never_match_each_other() -> None:
    """Negative control: ``father_of`` never matches ``mother_of``."""
    status, matched = _score("father_of", "mother_of", subject_gender="male")
    assert status == "missing"
    assert matched is None
    status, matched = _score("father_of", "mother_of", subject_gender="female")
    assert status == "missing"
    assert matched is None


def test_child_side_equivalence_follows_subject_gender() -> None:
    """``child_of`` ↔ ``daughter_of`` female; ↔ ``son_of`` male."""
    status, matched = _score("child_of", "daughter_of", subject_gender="female")
    assert status == "found"
    assert matched == "rel-1"
    status, matched = _score("son_of", "child_of", subject_gender="male")
    assert status == "found"
    assert matched == "rel-1"
    status, matched = _score("child_of", "son_of", subject_gender="female")
    assert status == "missing"
    assert matched is None


def test_grandparent_side_equivalence_follows_subject_gender() -> None:
    """``grandparent_of`` ↔ ``grandmother_of`` female; male stays missing."""
    status, matched = _score("grandmother_of", "grandparent_of", subject_gender="female")
    assert status == "found"
    assert matched == "rel-1"
    status, matched = _score("grandparent_of", "grandmother_of", subject_gender="male")
    assert status == "missing"
    assert matched is None


def test_sibling_side_equivalence_follows_subject_gender() -> None:
    """``sibling_of`` ↔ ``brother_of`` male; ↔ ``sister_of`` female."""
    status, matched = _score("sibling_of", "brother_of", subject_gender="male")
    assert status == "found"
    assert matched == "rel-1"
    status, matched = _score("sister_of", "sibling_of", subject_gender="female")
    assert status == "found"
    assert matched == "rel-1"
    status, matched = _score("sibling_of", "brother_of", subject_gender="female")
    assert status == "missing"
    assert matched is None


def test_exact_match_unaffected_by_unknown_gender() -> None:
    """Exact predicate equality matches regardless of gender (additive rule)."""
    status, matched = _score("father_of", "father_of", subject_gender=None)
    assert status == "found"
    assert matched == "rel-1"


def test_grandchild_vs_first_grandchild_is_no_gender_pair() -> None:
    """``grandchild_of`` ≠ ``first_grandchild_of`` even with known gender."""
    status, matched = _score("grandchild_of", "first_grandchild_of", subject_gender="female")
    assert status == "missing"
    assert matched is None


def test_unrelated_generic_pair_stays_missing() -> None:
    """Negative control: no equivalence outside the enumerated table."""
    status, matched = _score("colleague_of", "parent_of", subject_gender="male")
    assert status == "missing"
    assert matched is None
