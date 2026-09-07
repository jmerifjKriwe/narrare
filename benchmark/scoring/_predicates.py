"""Canonical fact-predicate folding and metadata-key lookup (Task 11).

Single home of the predicate-vocabulary layer consumed by the fact
matcher and its value-verification companion (``_value_match``):

- ``canonical_fact_predicate`` — snake_case normalization plus folding
  of known extraction variations onto the canonical reference predicate
  (``age`` → ``age_stated``, ``occupation``/``job_title`` →
  ``profession``). Unknown keys are returned normalized but unfolded —
  the matcher stays strict beyond the documented aliases.
- ``metadata_key`` — first metadata key (insertion order) folding to a
  canonical predicate.

Pure functions only — deterministic scoring, no wall-clock.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from benchmark.scoring.normalize import normalize_predicate

if TYPE_CHECKING:
    from collections.abc import Mapping

FACT_KEY_ALIASES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "age": "age_stated",
        "age_at_this_point": "age_stated",
        "age_in_chapter": "age_stated",
        "occupation": "profession",
        "job_title": "profession",
        "residence": "residence",
    }
)
"""Folding of observed extraction-key variations onto the canonical
reference predicate (the ``benchmark/corpus/reference`` registry).
Canonical keys map to themselves; unknown keys pass through unchanged.
Mirrors the canonical registry in ``narrare_core.kb.predicates`` (which
the benchmark must not import — co-evolution boundary)."""


def canonical_fact_predicate(value: str) -> str:
    """Normalize a fact predicate / metadata key to its canonical form."""
    predicate = normalize_predicate(value)
    return FACT_KEY_ALIASES.get(predicate, predicate)


def metadata_key(metadata: Mapping[str, object], predicate: str) -> str | None:
    """First metadata key (insertion order) folding to the predicate."""
    for key in metadata:
        if canonical_fact_predicate(key) == predicate:
            return key
    return None
