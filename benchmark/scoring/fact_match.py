"""Fact extraction + interval-aware fact matching (Task 11).

Where facts live in the OUT-03 record (``KbEntryDetail``): the KB entry
is semi-structured prose + metadata, so the scorer reads TWO evidence
planes, in strict precedence —

1. **Metadata rule** (structured): a metadata key whose
   ``normalize_predicate`` equals the fact's normalized predicate is
   predicate evidence; the fact is FOUND. It is CORRECT iff
   ``normalize_text(str(metadata[key])) == normalize_text(fact.value)``
   AND the interval check passes. A differing value or a contradicted
   interval = ``found_wrong`` (precision hit; evidence stays
   ``"metadata"`` — structured beats prose when both exist).
2. **Body rule** (prose): otherwise the fact is FOUND iff
   ``normalize_text(fact.value)`` is a substring of the normalized
   body. Correctness adds only the interval check: a substring match
   cannot carry a conflicting value by construction — the value IS the
   match. Body prose is deliberately NOT date-scanned (v1 tolerance:
   unparseable prose is no evidence and no contradiction).

Interval check (both rules): actual interval bounds are read from the
metadata companion keys ``{predicate}_from`` / ``{predicate}_to``,
falling back to ``valid_from`` / ``valid_to``; values parse via
``parse_date_value``. Comparison is month-precision with ±1 month
boundary tolerance (``normalize.boundary_matches``). Absent actual
bounds NEVER fail; a present-but-mismatched bound fails correctness.

Spurious facts: metadata keys of a matched entry whose normalized
predicate matches NO expected fact predicate of that entity — actual
structure the reference does not license. Sorted by entry + normalized
key for canonical determinism. Body prose never yields spurious facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
        predicate = normalize_predicate(fact.predicate)
        key = _metadata_key(actual.metadata, predicate)
        if key is not None:
            correct = _value_equal(str(actual.metadata[key]), fact.value) and _interval_ok(
                actual, fact
            )
            outcomes.append(_outcome(entity, fact, correct, "metadata"))
        elif normalize_text(fact.value) in actual.body:
            outcomes.append(_outcome(entity, fact, _interval_ok(actual, fact), "body"))
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
    """Metadata keys the entity's expected fact predicates do not license."""
    expected = {normalize_predicate(fact.predicate) for fact in entity.facts}
    rows = [
        SpuriousFact(entry_id=entry_id, entry_name=entry_name, key=key, value=str(value))
        for key, value in actual.metadata.items()
        if normalize_predicate(key) not in expected
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
    """First metadata key (insertion order) normalizing to the predicate."""
    for key in metadata:
        if normalize_predicate(key) == predicate:
            return key
    return None


def _value_equal(actual: str, expected: str) -> bool:
    return normalize_text(actual) == normalize_text(expected)


def _companion_bound(
    metadata: Mapping[str, object], predicate: str, side: str
) -> PartialDate | None:
    for key in (f"{predicate}_{side}", f"valid_{side}"):
        if key in metadata:
            parsed = parse_date_value(metadata[key])
            if parsed is not None:
                return parsed
    return None


def _interval_ok(actual: ActualFacts, fact: Fact) -> bool:
    """Month-precision interval check; absent actual bounds never fail."""
    predicate = normalize_predicate(fact.predicate)
    for ref_bound, side in ((fact.valid_from, "from"), (fact.valid_to, "to")):
        if ref_bound is None:
            continue
        actual_bound = _companion_bound(actual.metadata, predicate, side)
        if actual_bound is not None and not boundary_matches(ref_bound, actual_bound):
            return False
    return True
