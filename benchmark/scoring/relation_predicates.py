"""Relation predicate algebra: canonical forms + enumerated equivalences.

The predicate-level rules consumed by the ``relation_match`` scoring
loop. Every table here is an enumerated closed set — there is
deliberately no semantic synonym folding ("colleague_of" ≠
"neighbor_of"): vocabulary alignment happens in the extraction prompt,
not in scorer leniency. Split from ``relation_match`` per RULE-04
(predicate algebra vs. scoring loop are separate responsibilities).

Three equivalence kinds, all composable through ``generic_form``:

- same-direction gender pairs (``GENDER_EQUIVALENCE``, derived from the
  ``GENDER_FOLDS`` SSOT): ``parent_of`` ≡ ``father_of`` for a male
  shared subject;
- symmetric predicates (``SYMMETRIC_PREDICATES``): "A colleague_of B"
  ≡ "B colleague_of A" — the fact is orientation-free;
- swapped-endpoint inverse pairs (``SWAPPED_EQUIVALENCE``): applied
  AFTER folding both sides to their generic forms, so
  ``mother_of(A→B)`` ≡ ``daughter_of(B→A)`` iff A is female (fold of
  the reference side) AND B is female (fold of the edge side).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from benchmark.scoring.normalize import normalize_predicate

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.corpus_views import Gender

RELATION_ALIASES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "babysitter": "babysitter_of",
        "business_partner": "business_partner_of",
        "colleague": "colleague_of",
        "father": "father_of",
        "first_grandchild": "first_grandchild_of",
        "grandmother": "grandmother_of",
        "half_sibling": "half_sibling_of",
        "keeper": "keeper_of",
        "mother": "mother_of",
        "neighbor": "neighbor_of",
        "property_manager": "property_manager_of",
        "sibling": "sibling_of",
        "son": "son_of",
        "spouse": "spouse_of",
    }
)
"""Folding of bare role/kinship surfaces onto the canonical
``_of``-suffixed registry predicate (the
``benchmark/corpus/reference/relations.yaml`` forms). Canonical forms
and unknown predicates pass through unchanged; there is deliberately no
semantic synonym folding in THIS table (``brother_of`` never becomes
``sibling_of`` here). Mirrors the canonical registry in
``narrare_core.kb.predicates`` (which the benchmark must not import —
co-evolution boundary)."""

GENDER_FOLDS: Final[Mapping[str, tuple[str, Gender]]] = MappingProxyType(
    {
        "father_of": ("parent_of", "male"),
        "mother_of": ("parent_of", "female"),
        "son_of": ("child_of", "male"),
        "daughter_of": ("child_of", "female"),
        "grandfather_of": ("grandparent_of", "male"),
        "grandmother_of": ("grandparent_of", "female"),
        "brother_of": ("sibling_of", "male"),
        "sister_of": ("sibling_of", "female"),
    }
)
"""Gendered predicate → (generic predicate, required subject gender).

The single source of truth for gender-aware kinship equivalence: a
gendered predicate describes its subject, so it folds onto the generic
form iff THAT subject's corpus gender agrees (``generic_form``).
Enumerated closed set; two gendered predicates are never equivalent
directly (``father_of`` ≠ ``mother_of``), and ``grandchild_of`` vs
``first_grandchild_of`` is deliberately absent (different roles, not a
gender pair)."""

GENDER_EQUIVALENCE: Final[Mapping[frozenset[str], Gender]] = MappingProxyType(
    {
        frozenset((generic, gendered)): required
        for gendered, (generic, required) in GENDER_FOLDS.items()
    }
)
"""Same-direction gender pairs (derived view of ``GENDER_FOLDS``).

Key = one canonical predicate pair (generic side + gendered side);
value = the shared subject gender the pair's gendered predicate
requires (``father_of`` ⇒ male, ``mother_of`` ⇒ female, …). A reference
relation and an edge whose canonical predicates form such a pair match
IFF the shared subject resolves to that corpus gender (either
direction — the pair lookup is symmetric); an unknown/absent gender
stays strict."""

SYMMETRIC_PREDICATES: Final[frozenset[str]] = frozenset(
    {
        "sibling_of",
        "spouse_of",
        "engaged_to",
        "colleague_of",
        "friend_of",
        "neighbor_of",
        "confused_in_mail_with",
        "business_partner_of",
        "unrelated_to_family_of",
    }
)
"""Orientation-free predicates: "A R B" and "B R A" are the same fact,
so an edge with swapped endpoints matches as well (run
2026-09-07-clean-incremental-3 counted reversed sibling/spouse/
colleague edges spurious). Gendered forms compose through
``generic_form`` (``sibling_of`` ↔ reversed ``brother_of`` for a male
edge subject); directed kinship (``mother_of`` …) is deliberately NOT
symmetric."""

SWAPPED_EQUIVALENCE: Final[frozenset[frozenset[str]]] = frozenset(
    {
        frozenset({"parent_of", "child_of"}),
        frozenset({"grandparent_of", "grandchild_of"}),
    }
)
"""Inverse kinship pairs: match ONLY with endpoints swapped.

Composed with ``GENDER_FOLDS`` (both sides folded via their own
subject's gender first), this closed pair set covers exactly the
concrete inverse facts: ``mother_of``/``father_of``(A→B) ≡
``daughter_of``/``son_of``(B→A) with A's and B's genders agreeing,
``grandmother_of``/``grandfather_of``(A→B) ≡ ``grandchild_of``(B→A)
with A's gender agreeing (B unrestricted), and the generic
``parent_of``(A→B) ≡ ``child_of``(B→A). ``first_grandchild_of`` is
deliberately absent — birth order has no inverse."""


def canonical_relation_predicate(value: str) -> str:
    """Normalize a relationship predicate to the canonical registry form.

    Snake_case normalization first, then folding of documented bare
    surfaces onto their canonical ``_of`` form. Unknown predicates are
    returned normalized but unfolded.
    """
    predicate = normalize_predicate(value)
    return RELATION_ALIASES.get(predicate, predicate)


def generic_form(predicate: str, subject_gender: Gender | None) -> str:
    """Fold a gendered predicate onto its generic form.

    The fold applies iff the predicate's OWN subject resolves to the
    required corpus gender; an unknown/mismatched gender leaves the
    predicate unchanged (strict fallback).
    """
    fold = GENDER_FOLDS.get(predicate)
    if fold is None or subject_gender != fold[1]:
        return predicate
    return fold[0]


def predicates_match(
    reference_predicate: str,
    edge_predicate: str,
    subject_gender: Gender | None,
) -> bool:
    """Same-direction equality: exact, or an enumerated gender pair."""
    if reference_predicate == edge_predicate:
        return True
    required = GENDER_EQUIVALENCE.get(frozenset((reference_predicate, edge_predicate)))
    return required is not None and subject_gender == required


def swapped_predicates_match(
    reference_predicate: str,
    edge_predicate: str,
    subject_gender: Gender | None,
    edge_subject_gender: Gender | None,
) -> bool:
    """Swapped-endpoint equivalence (each side's own subject adjudicates).

    Both predicates fold to their generic forms first — the reference
    subject adjudicates the reference side, the edge subject (the
    reference object) adjudicates the edge side. Equal folded forms
    match iff the predicate is enumerated symmetric; different folded
    forms match iff they form an enumerated inverse pair.
    """
    ref_generic = generic_form(reference_predicate, subject_gender)
    edge_generic = generic_form(edge_predicate, edge_subject_gender)
    if ref_generic == edge_generic:
        return ref_generic in SYMMETRIC_PREDICATES
    return frozenset((ref_generic, edge_generic)) in SWAPPED_EQUIVALENCE
