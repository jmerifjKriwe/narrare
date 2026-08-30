"""Typed outputs of the KB build-quality scorer (Task 11).

Every expectation row carries the REFERENCE id it was scored against
(entity ids, F/PF/OF fact ids, R relation ids) and every spurious row
carries the ACTUAL identity (entry/edge id, name) — mechanical
traceability in both directions per the plan's Task 11 contract.

Aggregate conventions: coverage is ``0.0`` when nothing was expected
(nothing was scored, not a perfect run); precision is ``None`` when
nothing was found (undefined, not zero). Fact status is three-valued:
``found`` (evidence + correct value + interval), ``found_wrong``
(evidence, wrong value/interval — a precision hit), ``missing`` (no
evidence). All records are frozen with tuple sequences (deterministic
equality, ``out_records`` precedent).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EntityStatus = Literal["found", "missing"]
FactStatus = Literal["found", "found_wrong", "missing"]
RelationStatus = Literal["found", "missing"]
FactEvidence = Literal["metadata", "body"]


@dataclass(frozen=True)
class EntityOutcome:
    """One expected reference entity vs the actual KB listing."""

    ref_id: str
    ref_name: str
    status: EntityStatus
    matched_entry_id: str | None
    matched_via: str | None
    facts_expected: int
    facts_found: int
    facts_correct: int


@dataclass(frozen=True)
class FactOutcome:
    """One expected reference fact vs the actual evidence on its entity."""

    ref_id: str
    entity_ref_id: str
    predicate: str
    value: str
    status: FactStatus
    evidence: FactEvidence | None


@dataclass(frozen=True)
class RelationOutcome:
    """One expected reference relation vs the actual relationship edges."""

    ref_id: str
    subject: str
    predicate: str
    object: str
    status: RelationStatus
    matched_edge_id: str | None


@dataclass(frozen=True)
class SpuriousEntity:
    """An actual KB entry no expected entity claims (alias rule included)."""

    entry_id: str
    name: str


@dataclass(frozen=True)
class SpuriousFact:
    """Actual metadata structure no expected fact of the entity licenses."""

    entry_id: str
    entry_name: str
    key: str
    value: str


@dataclass(frozen=True)
class SpuriousRelation:
    """An actual relationship edge no expected relation claims."""

    edge_id: str
    rel_type: str
    source_name: str | None
    target_name: str | None


@dataclass(frozen=True)
class BuildQualityScore:
    """Aggregated build quality with fully itemized, traceable evidence."""

    entity_coverage: float
    fact_coverage: float
    fact_precision: float | None
    relation_coverage: float
    entities: tuple[EntityOutcome, ...]
    facts: tuple[FactOutcome, ...]
    relations: tuple[RelationOutcome, ...]
    spurious_entities: tuple[SpuriousEntity, ...]
    spurious_facts: tuple[SpuriousFact, ...]
    spurious_relations: tuple[SpuriousRelation, ...]
