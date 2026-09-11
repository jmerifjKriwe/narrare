"""Semantic text-value verification for fact matching (round 2).

The reference states a fact value in prose ("Projektarchitektin bei
Pfeiffer & Partner Architekten") while the KB legitimately splits the
same knowledge across a main key plus companion keys
(``profession_2016_2021`` = "Projektarchitektin (HafenCity, Hamburg)"
+ ``workplace`` = "Pfeiffer & Partner Architekten (seit März 2017)").

Matching rule — verification, NOT fuzzy scoring:

- Numeric references (digits after normalization) keep EXACT normalized
  equality — numbers are never token-relaxed (29 ≠ 30 stays a
  contradiction, and "29" stays exact against "29 Jahre").
- String references match when every stopword-stripped reference core
  token (``normalize.core_tokens``) appears across the candidate
  value's tokens plus the values of companion keys of the same
  predicate family (``COMPANION_PREDICATES``). Extra candidate tokens
  are legitimate elaboration; a missing reference token is no match —
  NO partial credit.

Pure functions only — deterministic scoring, no wall-clock.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from benchmark.scoring._predicates import metadata_key
from benchmark.scoring.normalize import core_tokens, is_numeric_text, normalize_text

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.corpus_views import Fact

COMPANION_PREDICATES: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        "profession": frozenset({"employer", "workplace"}),
        "residence": frozenset({"address", "lives_at"}),
    }
)
"""Predicate families whose values may complete a reference value's
core tokens. Keyed by the canonical reference predicate; the observed
run shape is ``profession`` + ``workplace``, ``employer`` per the
fix-round brief. Reverse directions are omitted deliberately: the
reference registry defines no ``employer``/``address``/``lives_at``
facts, so they can never be the scored predicate."""


def value_matches(actual: str, fact: Fact, metadata: Mapping[str, object], predicate: str) -> bool:
    """Whether the candidate value substantively states the reference value."""
    normalized_expected = normalize_text(fact.value)
    if is_numeric_text(normalized_expected):
        return normalize_text(actual) == normalized_expected
    pool = core_tokens(actual)
    for value in companion_values(metadata, predicate):
        pool |= core_tokens(value)
    return core_tokens(fact.value) <= pool


def companion_values(metadata: Mapping[str, object], predicate: str) -> tuple[str, ...]:
    """The candidate predicate's companion-family values (plain keys only)."""
    values: list[str] = []
    for companion in COMPANION_PREDICATES.get(predicate, frozenset()):
        key = metadata_key(metadata, companion)
        if key is not None:
            values.append(str(metadata[key]))
    return tuple(values)


def value_companion_keys(expected: set[str]) -> set[str]:
    """Value keys ``value_matches`` may consume for ``expected`` predicates.

    Companion family members are licensed because they are consumed as
    value evidence; plain canonical surfaces only — temporal companion
    variants stay spurious (the matcher does not consume them).
    """
    keys: set[str] = set()
    for predicate in expected:
        keys.update(COMPANION_PREDICATES.get(predicate, frozenset()))
    return keys
