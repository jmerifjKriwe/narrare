"""Relation predicate normalization regressions (Task 2 — predicate vocabulary).

Pins the canonical-form folding in ``relation_match``: bare role/kinship
surface forms ("mother", "business_partner") fold onto their canonical
``_of``-suffixed registry predicates before comparison, while genuinely
different predicates keep missing (no semantic synonym folding — the
scorer must stay strict; vocabulary alignment happens in the extraction
prompt, not here).
"""

from __future__ import annotations

from benchmark.scoring import score_build_quality
from benchmark.tests.scoring_helpers import (
    detail,
    edge,
    make_reference,
    ref_entity,
    ref_relation,
    summary,
)


def _score(reference_predicate: str, edge_rel_type: str) -> tuple[str, str | None]:
    """Score one relation against one two-endpoint KB with a single edge."""
    reference = make_reference(
        persons=(ref_entity("p1", "Ilse Meyer"), ref_entity("p2", "Anna Meyer")),
        relations=(ref_relation("R001", "p1", reference_predicate, "p2"),),
    )
    entries = (summary("e1", "Ilse Meyer"), summary("e2", "Anna Meyer"))
    details = (
        detail(
            "e1",
            name="Ilse Meyer",
            relationships=(edge("rel-1", edge_rel_type, "e1", "e2"),),
        ),
        detail("e2", name="Anna Meyer"),
    )
    score = score_build_quality(reference, entries, details)
    return score.relations[0].status, score.relations[0].matched_edge_id


def test_relation_folds_bare_mother_edge_to_mother_of() -> None:
    """Edge ``mother`` folds onto reference predicate ``mother_of``."""
    status, matched = _score("mother_of", "mother")
    assert status == "found"
    assert matched == "rel-1"


def test_relation_folds_bare_business_partner_edge() -> None:
    """Edge ``business_partner`` folds onto ``business_partner_of``."""
    status, matched = _score("business_partner_of", "business_partner")
    assert status == "found"
    assert matched == "rel-1"


def test_relation_canonical_forms_still_match_identity() -> None:
    """Canonical edge types keep matching unchanged (folding is additive)."""
    status, matched = _score("colleague_of", "colleague_of")
    assert status == "found"
    assert matched == "rel-1"


def test_relation_does_not_fold_semantic_synonyms() -> None:
    """Negative control: ``brother_of`` is NOT folded onto ``sibling_of``."""
    status, matched = _score("sibling_of", "brother_of")
    assert status == "missing"
    assert matched is None


def test_relation_unfolded_invented_type_stays_spurious() -> None:
    """An edge with an unfolded invented type is itemized as spurious."""
    reference = make_reference(
        persons=(ref_entity("p1", "Ilse Meyer"), ref_entity("p2", "Anna Meyer")),
        relations=(ref_relation("R001", "p1", "mother_of", "p2"),),
    )
    entries = (summary("e1", "Ilse Meyer"), summary("e2", "Anna Meyer"))
    details = (
        detail(
            "e1",
            name="Ilse Meyer",
            relationships=(edge("rel-9", "family_helper", "e1", "e2"),),
        ),
        detail("e2", name="Anna Meyer"),
    )
    score = score_build_quality(reference, entries, details)
    assert score.relations[0].status == "missing"
    assert len(score.spurious_relations) == 1
    assert score.spurious_relations[0].edge_id == "rel-9"
    assert score.spurious_relations[0].rel_type == "family_helper"
