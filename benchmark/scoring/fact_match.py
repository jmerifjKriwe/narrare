"""Fact extraction + interval-aware fact matching (Task 11).

Where facts live in the OUT-03 record (``KbEntryDetail``): the KB entry
is semi-structured prose + metadata, so the scorer reads TWO evidence
planes, in strict precedence — entry ``tags`` are explicitly excluded
from both planes (tags carry no predicate binding: neither fact
evidence nor spurious-fact material):

1. **Metadata rule** (structured): a metadata key whose canonical
   predicate (``canonical_fact_predicate``: snake_case normalization
   plus folding of known extraction variations — ``age`` →
   ``age_stated``, ``occupation``/``job_title`` → ``profession``) equals
   the fact's canonical predicate is predicate evidence; the fact is
   FOUND. It is CORRECT iff
   ``normalize_text(str(metadata[key])) == normalize_text(fact.value)``
   AND the interval check passes. A differing value or a contradicted
   interval = ``found_wrong`` (precision hit; evidence stays
   ``"metadata"`` — structured beats prose when both exist).

   **Temporal year keys**: time-varying facts (a bounded fact, or a
   predicate recurring across the entity's snapshot facts) additionally
   accept a year-suffixed metadata key (``age_2017: 25``) whose year
   lies within the fact's reference interval — the KB deliberately
   keeps the LATEST value under the plain key and the historical
   progression under year-suffixed keys, so a snapshot fact is
   satisfied by EITHER the plain key OR its year-suffixed variant. On
   the year-key path the suffix year IS the temporal anchor: year
   containment replaces the companion-bound interval check. A value
   match under an out-of-bounds year is a ``found_wrong`` contradiction.
2. **Body rule** (prose): otherwise the fact is FOUND iff the
   normalized value occurs as a whole token run in the normalized body
   (boundary-aware membership — ``"24"`` never matches inside
   ``"2024"``). Correctness adds only the interval check: a
   boundary-aware token-run match cannot carry a conflicting value by
   construction — the value IS the match. Body prose is deliberately
   NOT date-scanned (v1 tolerance: unparseable prose is no evidence and
   no contradiction).

Interval check (both rules): actual interval bounds are read from the
metadata companion keys ``{predicate}_from`` / ``{predicate}_to`` —
probed under the matched key's surface form, the canonical predicate,
and the generic ``valid_from`` / ``valid_to`` —; values parse via
``parse_date_value``. Comparison is month-precision with ±1 month
boundary tolerance (``normalize.boundary_matches``). Absent actual
bounds NEVER fail; a present-but-mismatched bound fails correctness.

Spurious facts: metadata keys of a matched entry whose canonical
predicate matches NO expected fact predicate of that entity — actual
structure the reference does not license. Companion interval keys
consumed as interval evidence (``{predicate}_from`` / ``{predicate}_to``
under canonical AND alias surfaces, plus the generic ``valid_from`` /
``valid_to``) are licensed by construction and exempt. Year-suffixed
temporal keys (``age_2017``) are exempt when their stripped surface
folds onto a time-varying expected predicate. Sorted by entry +
normalized key for canonical determinism. Body prose never yields
spurious facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from benchmark.scoring.normalize import (
    boundary_matches,
    normalize_predicate,
    normalize_text,
    parse_date_value,
)
from benchmark.scoring.score_records import FactEvidence, FactOutcome, SpuriousFact

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.corpus_views import Entity, Fact, PartialDate
    from benchmark.drivers.out_records import KbEntryDetail

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
    """Normalize a fact predicate / metadata key to its canonical form.

    Snake_case normalization first, then folding of known extraction
    variations onto the reference predicate. Unknown keys are returned
    normalized but unfolded — the matcher stays strict beyond the
    documented aliases.
    """
    predicate = normalize_predicate(value)
    return FACT_KEY_ALIASES.get(predicate, predicate)


@dataclass(frozen=True)
class ActualFacts:
    """The fact-evidence planes extracted from one ``KbEntryDetail``."""

    metadata: Mapping[str, object]
    body: str  # already normalized


def actual_facts_from(entry: KbEntryDetail) -> ActualFacts:
    """Extract the evidence planes from an entry detail."""
    return ActualFacts(
        metadata=entry.metadata if entry.metadata is not None else {},
        body=normalize_text(entry.body) if entry.body is not None else "",
    )


def score_facts(entity: Entity, actual: ActualFacts) -> tuple[FactOutcome, ...]:
    """Score every expected fact of one entity against the evidence planes."""
    outcomes: list[FactOutcome] = []
    for fact in entity.facts:
        predicate = canonical_fact_predicate(fact.predicate)
        key = _metadata_key(actual.metadata, predicate)
        if key is not None and _value_equal(str(actual.metadata[key]), fact.value):
            correct = _interval_ok(actual, fact, key)
            outcomes.append(_outcome(entity, fact, correct, "metadata"))
            continue
        temporal_key = (
            _temporal_year_key(actual.metadata, fact, predicate)
            if _is_temporal_fact(fact, entity)
            else None
        )
        if temporal_key is not None:
            _, satisfied = temporal_key
            outcomes.append(_outcome(entity, fact, satisfied, "metadata"))
        elif key is not None:
            # Plain key exists with a differing value and no year-key rescue.
            outcomes.append(_outcome(entity, fact, False, "metadata"))
        elif _body_contains(actual.body, fact.value):
            outcomes.append(
                _outcome(entity, fact, _interval_ok(actual, fact, actual_key=""), "body")
            )
        else:
            outcomes.append(
                FactOutcome(
                    ref_id=fact.id,
                    entity_ref_id=entity.id,
                    predicate=fact.predicate,
                    value=fact.value,
                    status="missing",
                    evidence=None,
                )
            )
    return tuple(outcomes)


def spurious_facts(
    entity: Entity, actual: ActualFacts, entry_id: str, entry_name: str
) -> tuple[SpuriousFact, ...]:
    """Metadata keys the entity's expected fact predicates do not license.

    Companion interval keys consumed as interval evidence
    (``{predicate}_from``/``{predicate}_to`` under canonical and alias
    surfaces plus the generic ``valid_from``/``valid_to``) are licensed
    by construction, as are year-suffixed temporal keys for time-varying
    expected predicates.
    """
    expected = {canonical_fact_predicate(fact.predicate) for fact in entity.facts}
    licensed = expected | _interval_companion_keys(expected)
    temporal = {
        canonical_fact_predicate(fact.predicate)
        for fact in entity.facts
        if _is_temporal_fact(fact, entity)
    }
    rows = [
        SpuriousFact(entry_id=entry_id, entry_name=entry_name, key=key, value=str(value))
        for key, value in actual.metadata.items()
        if not _licensed_key(key, licensed, temporal)
    ]
    return tuple(sorted(rows, key=lambda row: (row.entry_id, normalize_predicate(row.key))))


def _outcome(entity: Entity, fact: Fact, correct: bool, evidence: FactEvidence) -> FactOutcome:
    return FactOutcome(
        ref_id=fact.id,
        entity_ref_id=entity.id,
        predicate=fact.predicate,
        value=fact.value,
        status="found" if correct else "found_wrong",
        evidence=evidence,
    )


def _metadata_key(metadata: Mapping[str, object], predicate: str) -> str | None:
    """First metadata key (insertion order) folding to the predicate."""
    for key in metadata:
        if canonical_fact_predicate(key) == predicate:
            return key
    return None


def _body_contains(body: str, value: str) -> bool:
    """Whole-token-run membership, never character-level.

    ``normalize_text`` has already collapsed every non-alphanumeric run
    to a single space on both sides, so padding each side with one space
    makes the containment token-boundary exact: ``"24"`` cannot match
    inside ``"2024"``, while multi-word values (``"hcu hamburg"``) still
    match ``"HCU-Hamburg"``.
    """
    return f" {normalize_text(value)} " in f" {body} "


def _interval_companion_keys(expected: set[str]) -> set[str]:
    """Interval keys ``_companion_bound`` may consume for ``expected`` predicates.

    Companion keys are licensed under the canonical predicate AND under
    every alias surface that folds onto an expected predicate.
    """
    alias_surfaces = {a for a, p in FACT_KEY_ALIASES.items() if p in expected}
    keys = {"valid_from", "valid_to"}
    for predicate in expected | alias_surfaces:
        keys.update(f"{predicate}_{side}" for side in ("from", "to"))
    return keys


def _is_temporal_fact(fact: Fact, entity: Entity) -> bool:
    """A time-varying fact: bounded, or a predicate recurring as snapshots.

    Only temporal facts accept year-suffixed metadata keys — the plain
    rule stays strict for atemporal predicates.
    """
    if not fact.source_chapters:
        return False
    if fact.valid_from is not None or fact.valid_to is not None:
        return True
    predicate = canonical_fact_predicate(fact.predicate)
    return (
        sum(1 for other in entity.facts if canonical_fact_predicate(other.predicate) == predicate)
        > 1
    )


def _temporal_year_key(
    metadata: Mapping[str, object], fact: Fact, predicate: str
) -> tuple[str, bool] | None:
    """First value-matching year key as ``(key, satisfied)``, else ``None``.

    An in-bounds year wins over any out-of-bounds match; ``satisfied``
    marks whether the key's year lies within the fact's reference
    interval (``True`` → found, ``False`` → found_wrong contradiction).
    """
    contradicted: tuple[str, bool] | None = None
    for key in metadata:
        year = _year_suffix(key)
        if year is None or canonical_fact_predicate(key.removesuffix(f"_{year}")) != predicate:
            continue
        if not _value_equal(str(metadata[key]), fact.value):
            continue
        if _year_in_bounds(fact, year):
            return key, True
        contradicted = contradicted or (key, False)
    return contradicted


def _year_suffix(key: str) -> int | None:
    """Trailing ``_<year>`` component (``age_2017`` → 2017), else ``None``."""
    _, separator, year = key.rpartition("_")
    if separator and len(year) == 4 and year.isdigit():
        return int(year)
    return None


def _year_in_bounds(fact: Fact, year: int) -> bool:
    """Year-precision containment of the key's year in the fact's interval."""
    lower = fact.valid_from.year if fact.valid_from is not None else None
    upper = fact.valid_to.year if fact.valid_to is not None else None
    return (lower is None or year >= lower) and (upper is None or year <= upper)


def _licensed_key(key: str, licensed: set[str], temporal: set[str]) -> bool:
    """Plain, companion-interval, or year-suffixed temporal key licensing."""
    if canonical_fact_predicate(key) in licensed:
        return True
    year = _year_suffix(key)
    if year is None:
        return False
    surface = canonical_fact_predicate(key.removesuffix(f"_{year}"))
    return surface in temporal


def _value_equal(actual: str, expected: str) -> bool:
    return normalize_text(actual) == normalize_text(expected)


def _companion_bound(
    metadata: Mapping[str, object], predicate: str, actual_key: str, side: str
) -> PartialDate | None:
    probes = (f"{actual_key}_{side}", f"{predicate}_{side}", f"valid_{side}")
    for key in filter(None, probes):
        if key in metadata:
            parsed = parse_date_value(metadata[key])
            if parsed is not None:
                return parsed
    return None


def _interval_ok(actual: ActualFacts, fact: Fact, actual_key: str) -> bool:
    """Month-precision interval check; absent actual bounds never fail.

    Bounds are probed under the matched metadata key's surface form
    (so an alias key ``age`` can carry ``age_from``), the canonical
    predicate, and the generic ``valid_*`` keys.
    """
    predicate = canonical_fact_predicate(fact.predicate)
    for ref_bound, side in ((fact.valid_from, "from"), (fact.valid_to, "to")):
        if ref_bound is None:
            continue
        actual_bound = _companion_bound(actual.metadata, predicate, actual_key, side)
        if actual_bound is not None and not boundary_matches(ref_bound, actual_bound):
            return False
    return True
