"""Per-capability retrieval coverage rows for the run artifacts (Task 13).

The partial-benchmarkability mapping (brief requirement 3): scored ONLY
on mechanically comparable surfaces, per the inventory's benchmarkable
verdicts (``benchmark/inventory/02-out.md``). ``_SURFACE_ROWS`` is the
static per-capability table — ``scored`` (the parsed record is a
scoring input here), ``recorded`` (driven, output kept for the
artifacts but not scored by retrieval, with the reason and the scorer
that DOES handle it where one exists), ``skipped`` (with the structural
reason). ``coverage_rows`` merges the derived ``driven`` flags: whether
a record THIS scorer consumes was supplied (CAP-OUT-03 details,
CAP-OUT-07 timeline). Runner-level drivenness of the remaining
capabilities is the runner's ledger (Tasks 14/15), not re-derived here.

Pure data + a pure merge — deterministic by construction.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Final

from benchmark.scoring.retrieval_records import CapabilityCoverage

if TYPE_CHECKING:
    from benchmark.drivers.out_records import EntityDetailRecord, TimelineReadRecord

_SURFACE_ROWS: Final[tuple[CapabilityCoverage, ...]] = (
    CapabilityCoverage(
        capability="CAP-OUT-01",
        surface="recorded",
        driven=False,
        reason=("entry listing is scored by build-quality (Task 11); retrieval consumes no record"),
    ),
    CapabilityCoverage(
        capability="CAP-OUT-02",
        surface="recorded",
        driven=False,
        reason=(
            "lexical probe search is mechanically comparable (inventory: yes) but the v1 "
            "query set samples entity facts/relations only; the record establishes "
            "drivenness; free-text scoring deferred"
        ),
    ),
    CapabilityCoverage(
        capability="CAP-OUT-03",
        surface="scored",
        driven=False,
        reason=(
            "entity detail + relationships answer entity_lookup/state_at_time/relationship queries"
        ),
    ),
    CapabilityCoverage(
        capability="CAP-OUT-04",
        surface="recorded",
        driven=False,
        reason=(
            "graph structure and path probes recorded; "
            "scoring deferred (no reference graph projection)"
        ),
    ),
    CapabilityCoverage(
        capability="CAP-OUT-05",
        surface="skipped",
        driven=False,
        reason=(
            "series canon skipped: corpus provides no series (structural gating, plan Task 10)"
        ),
    ),
    CapabilityCoverage(
        capability="CAP-OUT-06",
        surface="recorded",
        driven=False,
        reason=(
            "wiki prose recorded-not-scored: presence/freshness scorable, "
            "summary text needs an LLM judge (inventory: partially benchmarkable)"
        ),
    ),
    CapabilityCoverage(
        capability="CAP-OUT-07",
        surface="recorded",
        driven=False,
        reason=(
            "timeline events/ages are mechanically comparable (inventory: yes) but v1 "
            "queries sample entity facts and relations only; the record establishes "
            "drivenness; event-set scoring deferred"
        ),
    ),
    CapabilityCoverage(
        capability="CAP-OUT-08",
        surface="recorded",
        driven=False,
        reason=(
            "suggestion ranking recorded; relevance-set scoring deferred (no reference sets in v1)"
        ),
    ),
    CapabilityCoverage(
        capability="CAP-OUT-09",
        surface="recorded",
        driven=False,
        reason=(
            "mention-resolution link set recorded; scoring deferred "
            "(no reference mention map in v1)"
        ),
    ),
    CapabilityCoverage(
        capability="CAP-OUT-10",
        surface="recorded",
        driven=False,
        reason=("template reads driven; static schema, no KB content answering retrieval queries"),
    ),
)

__all__ = [
    "coverage_rows",
]


def coverage_rows(
    details: tuple[EntityDetailRecord, ...], timeline: TimelineReadRecord | None
) -> tuple[CapabilityCoverage, ...]:
    """Static surface verdicts merged with the derived driven flags."""
    driven = {"CAP-OUT-03": bool(details), "CAP-OUT-07": timeline is not None}
    return tuple(replace(row, driven=driven.get(row.capability, False)) for row in _SURFACE_ROWS)
