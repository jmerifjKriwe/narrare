"""Typed outputs of the retrieval scorer (Task 13).

One frozen record per concern, mirroring the ``score_records`` precedent:

- ``RetrievalQuery`` — a reference-derived query; ``ref_id`` is the
  traceable reference id (``F*``/``R*``), ``expected`` the reference
  value (fact value, or the object entity's name for a relationship),
  and the own ``valid_from``/``valid_to`` bounds ride along for the
  explicit interval riders.
- ``AnswerOutcome`` — the KB's answer to one query; ``answered_by``
  carries the ACTUAL identity (entry id / edge id) for mechanical
  traceability, ``interval_checked`` reports whether interval evidence
  was actually verified (``False`` = honest downgrade, never a
  fabricated pass).
- ``CapabilityCoverage`` — one artifacts-table row: the per-capability
  retrieval surface verdict (``scored`` / ``recorded`` / ``skipped`` +
  reason, per the inventory's benchmarkable verdicts) and the driven
  flag derived from the records this scorer consumes.
- ``RetrievalScore`` — aggregates follow the ``BuildQualityScore``
  conventions: coverage is ``0.0`` when nothing was queried (nothing
  scored, not a perfect run); precision is ``None`` when nothing was
  found (undefined, not zero).

All records are frozen with tuple sequences (deterministic equality).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from benchmark.corpus_views import PartialDate

QueryKind = Literal["entity_lookup", "state_at_time", "relationship"]
AnswerStatus = Literal["found", "found_wrong", "missing"]
Surface = Literal["scored", "recorded", "skipped"]


@dataclass(frozen=True)
class RetrievalQuery:
    """One reference-derived retrieval query (deterministic generation)."""

    ref_id: str
    kind: QueryKind
    entity_ref: str
    entity_name: str
    predicate: str
    expected: str
    valid_from: PartialDate | None
    valid_to: PartialDate | None


@dataclass(frozen=True)
class AnswerOutcome:
    """The KB's answer to one query, matched with the T11 fact rules."""

    ref_id: str
    kind: QueryKind
    status: AnswerStatus
    interval_checked: bool
    answered_by: str | None


@dataclass(frozen=True)
class CapabilityCoverage:
    """One artifacts-table row: how retrieval scoring treats a capability."""

    capability: str
    surface: Surface
    driven: bool
    reason: str


@dataclass(frozen=True)
class RetrievalScore:
    """Aggregated retrieval score with fully itemized, traceable evidence."""

    queries: tuple[RetrievalQuery, ...]
    outcomes: tuple[AnswerOutcome, ...]
    coverage: tuple[CapabilityCoverage, ...]
    answer_coverage: float
    answer_precision: float | None
