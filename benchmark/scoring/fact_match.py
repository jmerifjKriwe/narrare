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
   FOUND. It is CORRECT iff ``value_matches`` holds (see below) AND the
   interval check passes. A differing value or a contradicted
   interval = ``found_wrong`` (precision hit; evidence stays
   ``"metadata"`` — structured beats prose when both exist).

   **Value matching (round 2)**: numeric references (digits after
   normalization) keep EXACT normalized equality — numbers are never
   token-relaxed. String references verify the knowledge is
   substantively present: every stopword-stripped reference core token
   (``normalize.core_tokens``) must appear across the candidate value's
   tokens PLUS the values of companion keys of the same predicate
   family (``COMPANION_PREDICATES``: profession ↔ employer/workplace,
   residence ↔ address/lives_at — the KB legitimately splits
   "Projektarchitektin bei Pfeiffer & Partner Architekten" into
   ``profession_2016_2021`` = "Projektarchitektin (HafenCity, Hamburg)"
   + ``workplace``). NO partial credit: a missing reference token is no
   match — this is verification, not fuzzy scoring. Companion value
   keys consumed this way are licensed in the spurious plane.

   **Temporal year keys (round 2 grammar)**: time-varying facts (a
   bounded fact, or a predicate recurring across the entity's snapshot
   facts) additionally accept temporal-suffixed metadata keys, parsed
   by regex in ``_temporal_keys``: ``pred_YYYY`` (``age_2017``),
   ``pred_YYYY_M`` (``age_2019_12``; the month does not tighten
   coverage), and ``pred_YYYY1_YYYY2`` ranges
   (``profession_2016_2021``). A key matches when its year set covers
   the fact's temporal position (``covers_year``: key year within the
   fact's reference interval; range keys cover the fact's anchor year).
   The KB deliberately keeps the LATEST value under the plain key and
   historical progression under suffixed keys, so a snapshot fact is
   satisfied by EITHER the plain key OR a temporal variant. On the
   temporal path the key's year IS the temporal anchor: year coverage
   replaces the companion-bound interval check. A value match under an
   out-of-coverage key is a ``found_wrong`` contradiction. Temporal
   keys are licensed in the spurious plane exactly for time-varying
   expected predicates, in all three grammar forms.
2. **Inverse residence rule (round 3)**: reference ``residence_of``
   facts live on PLACE entities with entity-id values, while the KB
   states the binding on the PERSON entry's residence keys. When the
   direct paths fail, the fact is FOUND iff the referenced person's
   entry metadata carries a residence-family key (``residence`` /
   ``lives_at``, plain or temporal-variant) whose value contains the
   place's core tokens (``RESIDENCE_INVERSE_FAMILY``). Interval bounds
   are not probed on this path (v1 tolerance: the person-side
   ``residence`` fact carries the interval evidence and is scored
   separately).
3. **Body rule** (prose): otherwise the fact is FOUND iff the
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
``valid_to``) are licensed by construction and exempt. Companion VALUE
keys of an expected predicate's family (``COMPANION_PREDICATES``) are
licensed — they are consumed as value evidence. Temporal-suffixed keys
(all three grammar forms of ``_temporal_keys.parse_temporal_key``) are
exempt when their stripped surface folds onto a time-varying expected
predicate. Sorted by entry + normalized key for canonical determinism.
Body prose never yields spurious facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from benchmark.scoring._predicates import (
    FACT_KEY_ALIASES,
    canonical_fact_predicate,
    metadata_key,
)
from benchmark.scoring._temporal_keys import covers_year, parse_temporal_key
from benchmark.scoring._value_match import value_companion_keys, value_matches
from benchmark.scoring.normalize import (
    boundary_matches,
    core_tokens,
    normalize_predicate,
    normalize_text,
    parse_date_value,
)
from benchmark.scoring.score_records import FactEvidence, FactOutcome, SpuriousFact

if TYPE_CHECKING:
    from collections.abc import Mapping

    from benchmark.corpus_views import Entity, Fact, PartialDate
    from benchmark.drivers.out_records import KbEntryDetail

RESIDENCE_INVERSE_FAMILY: Final[frozenset[str]] = frozenset({"residence", "lives_at"})
"""Canonical predicates accepted as inverse evidence for ``residence_of``
place facts (fact-match round 3): the person entry's binding."""


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


def score_facts(
    entity: Entity,
    actual: ActualFacts,
    inverse_residences: Mapping[str, Mapping[str, object]] | None = None,
) -> tuple[FactOutcome, ...]:
    """Score every expected fact of one entity against the evidence planes.

    ``inverse_residences`` (fact-match round 3) maps reference entity id
    → that entity's matched entry metadata; it carries the cross-entity
    evidence for the inverse residence rule and may be omitted when no
    inverse evidence exists.
    """
    outcomes: list[FactOutcome] = []
    for fact in entity.facts:
        predicate = canonical_fact_predicate(fact.predicate)
        key = metadata_key(actual.metadata, predicate)
        if key is not None and value_matches(
            str(actual.metadata[key]), fact, actual.metadata, predicate
        ):
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
        elif _inverse_residence_found(fact, entity, inverse_residences):
            outcomes.append(_outcome(entity, fact, True, "metadata"))
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
    licensed = expected | _interval_companion_keys(expected) | value_companion_keys(expected)
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
    """First value-matching temporal key as ``(key, satisfied)``, else ``None``.

    Candidates are parsed by regex (all three grammar forms of
    ``parse_temporal_key``). An in-coverage key wins over any
    out-of-coverage match; ``satisfied`` marks whether the key's year
    set covers the fact's temporal position (``True`` → found,
    ``False`` → found_wrong contradiction). Candidates whose value does
    not substantively match are skipped — a different snapshot year is
    no contradiction.
    """
    contradicted: tuple[str, bool] | None = None
    for key in metadata:
        parsed = parse_temporal_key(key)
        if parsed is None or canonical_fact_predicate(parsed.predicate) != predicate:
            continue
        if not value_matches(str(metadata[key]), fact, metadata, predicate):
            continue
        if covers_year(parsed, fact):
            return key, True
        contradicted = contradicted or (key, False)
    return contradicted


def _licensed_key(key: str, licensed: set[str], temporal: set[str]) -> bool:
    """Plain, companion, or temporal-suffixed key licensing.

    Temporal keys (all grammar forms) are licensed when their stripped
    surface folds onto a time-varying expected predicate.
    """
    if canonical_fact_predicate(key) in licensed:
        return True
    parsed = parse_temporal_key(key)
    if parsed is None:
        return False
    return canonical_fact_predicate(parsed.predicate) in temporal


def _inverse_residence_found(
    fact: Fact,
    entity: Entity,
    inverse_residences: Mapping[str, Mapping[str, object]] | None,
) -> bool:
    """Inverse residence evidence (round 3): the person entry states the binding.

    For a ``residence_of`` fact on a place entity (value = reference
    person id), the fact is satisfied when the person's entry metadata
    carries a residence-family key (``residence``/``lives_at``, plain or
    temporal-variant surface) whose value contains ALL of the place's
    core tokens. Interval bounds are not probed here (v1 tolerance —
    the person-side ``residence`` fact is scored separately).
    """
    if inverse_residences is None or canonical_fact_predicate(fact.predicate) != "residence_of":
        return False
    person_metadata = inverse_residences.get(fact.value)
    if person_metadata is None:
        return False
    place_tokens = core_tokens(entity.name)
    if not place_tokens:
        return False
    for key, value in person_metadata.items():
        if _residence_family_surface(key) is None:
            continue
        if place_tokens <= core_tokens(str(value)):
            return True
    return False


def _residence_family_surface(key: str) -> str | None:
    """The key's canonical predicate when it belongs to the residence family.

    Accepts plain keys (``residence``) and temporal-variant surfaces
    (``residence_2019``) via the shared temporal grammar; unrelated
    stripped surfaces (``residence_of_childhood``) never fold in.
    """
    parsed = parse_temporal_key(key)
    surface = parsed.predicate if parsed is not None else key
    canonical = canonical_fact_predicate(surface)
    return canonical if canonical in RESIDENCE_INVERSE_FAMILY else None


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
