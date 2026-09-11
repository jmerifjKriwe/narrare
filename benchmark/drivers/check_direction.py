"""CHECK-direction capability drivers — novel surfaces + facade (Task 10).

This module owns the two novel-surface check drivers: the KB consistency
report (CAP-CHK-01, ``kb/router_consistency.py``) and the temporal
timeline consistency (CAP-CHK-04, ``planning/router_timeline_analysis.py``).
The series-scope REST half (CAP-CHK-02/03) lives in
``benchmark.drivers.check_direction_series``, the SSE half
(CAP-CHK-05..07) in ``benchmark.drivers.check_direction_streams``; THIS
module is the direction's registration facade — ``CHECK_DIRECTION_DRIVERS``
(the cap_id → driver class map wired into ``benchmark.drivers``) is
assembled here from all three halves (RULE-04 split, facade precedent:
``benchmark.drivers.out_direction``).

Shared rules (module docstring of ``benchmark.drivers.in_parsing``):
every driver invokes exactly its registry ``EndpointSpec`` surface via
the shape helpers, parses responses into the typed records of
``benchmark.drivers.check_records``, and returns a ``CapabilityResult``
whose ``parsed`` carries that record; raw exchanges flow to the run
sink. A missing structural target (series/chapter ids the run could not
discover) → ``SKIPPED(structural)``; transport/HTTP/SSE/shape failures →
``ERROR`` with a reason.

Structural requirements (router-verified, encoded in the drivers):

- CAP-CHK-01 runs on the run's own novel KB — no series, always drivable.
  The request pins ``refresh=true`` (the check is cached server-side with
  a 10-minute TTL — a re-run must never replay a stale report) and all
  three analysis stages (entry-internal + asymmetry + cross-entity) for
  the complete detection surface.
- CAP-CHK-04 runs on the run's own timeline (KB-enriched with character
  birth dates) — a plain GET, always drivable.
- CAP-CHK-02/03 need a series the novel is JOINED to (service-verified
  membership) — gated on ``targets['series_id']``; see the series module
  docstring. The single-novel run CAN provide that via the series
  lifecycle prerequisite (map §7), so neither is hard-skipped by design.
- CAP-CHK-05 needs the run's first ingested chapter
  (``targets['chapter_id']``); CAP-CHK-06/07 are novel-scoped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.drivers.check_direction_series import (
    SeriesConsistencyDriver,
    SeriesVoiceDriftDriver,
)
from benchmark.drivers.check_direction_streams import (
    AuthorVoiceDriftDriver,
    VoiceCheckDriver,
    VoiceDriftDriver,
)
from benchmark.drivers.check_records import (
    ConsistencyCheckRecord,
    ConsistencyIssueFinding,
    TemporalConsistencyRecord,
    TemporalIssue,
)
from benchmark.drivers.in_parsing import (
    StreamProtocolError,
    as_bool,
    as_float,
    as_int,
    as_list,
    as_opt_object,
    as_opt_text,
    as_str_tuple,
    as_text,
    guarded,
    response_field,
)
from benchmark.drivers.shapes import invoke_rest

if TYPE_CHECKING:
    from benchmark.drivers.base import CapabilityContext, CapabilityDriver, CapabilityResult


def _summary_pairs(raw: object) -> tuple[tuple[str, int], ...]:
    """``dict[str, int]`` → key-sorted tuple pairs (deterministic equality)."""
    counts = as_opt_object(response_field(raw, "summary"))
    if counts is None:
        raise StreamProtocolError("response shape drift: expected a summary object")
    return tuple(sorted((as_text(key), as_int(value)) for key, value in counts.items()))


# ---------------------------------------------------------------------------
# CAP-CHK-01 — ConsistencyCheckDriver: combined KB consistency report
# ---------------------------------------------------------------------------


def _issue(body: object) -> ConsistencyIssueFinding:
    """``ConsistencyIssue`` (kb/worldbuilding_contracts.py) — complete."""
    return ConsistencyIssueFinding(
        finding_index=as_int(response_field(body, "finding_index")),
        category=as_text(response_field(body, "category")),
        entity_ids=as_str_tuple(response_field(body, "entity_ids")),
        entity_names=as_str_tuple(response_field(body, "entity_names")),
        description=as_text(response_field(body, "description")),
        contradiction=as_text(response_field(body, "contradiction")),
        suggested_resolution=as_opt_text(response_field(body, "suggested_resolution")),
        severity=as_text(response_field(body, "severity")),
        confidence=as_float(response_field(body, "confidence")),
    )


def _drive_consistency_check(ctx: CapabilityContext) -> ConsistencyCheckRecord:
    checked = invoke_rest(
        ctx,
        step="CAP-CHK-01",
        method="POST",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/consistency-check",
        json_body={
            "entity_types": None,
            "include_entry_internal": True,
            "include_asymmetry": True,
            "include_cross_entity": True,
            "refresh": True,
        },
    )
    return ConsistencyCheckRecord(
        novel_id=as_text(response_field(checked, "novel_id")),
        entity_count=as_int(response_field(checked, "entity_count")),
        issues=tuple(
            _issue(issue) for issue in as_list(response_field(checked, "issues"), "issue list")
        ),
        summary=_summary_pairs(checked),
        suppressed_count=as_int(response_field(checked, "suppressed_count")),
    )


class ConsistencyCheckDriver:
    """CAP-CHK-01 — full-refresh consistency report over the run's KB."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-CHK-01", ctx, _drive_consistency_check)


# ---------------------------------------------------------------------------
# CAP-CHK-04 — TemporalConsistencyDriver: timeline issues (deterministic+LLM)
# ---------------------------------------------------------------------------


def _temporal_issue(body: object) -> TemporalIssue:
    """``TemporalIssueResponse`` (planning/timeline_schemas.py) — complete."""
    return TemporalIssue(
        severity=as_text(response_field(body, "severity")),
        rule_id=as_text(response_field(body, "rule_id")),
        event_ids=as_str_tuple(response_field(body, "event_ids")),
        description=as_text(response_field(body, "description")),
        suggestion=as_text(response_field(body, "suggestion")),
        source=as_text(response_field(body, "source")),
    )


def _drive_temporal_consistency(ctx: CapabilityContext) -> TemporalConsistencyRecord:
    checked = invoke_rest(
        ctx,
        step="CAP-CHK-04",
        method="GET",
        path=f"/api/v1/planning/timeline/{ctx.novel_id}/consistency",
    )
    return TemporalConsistencyRecord(
        issues=tuple(
            _temporal_issue(issue)
            for issue in as_list(response_field(checked, "issues"), "issue list")
        ),
        deterministic_pass=as_bool(response_field(checked, "deterministic_pass")),
        overall_assessment=as_text(response_field(checked, "overall_assessment")),
    )


class TemporalConsistencyDriver:
    """CAP-CHK-04 — temporal consistency incl. duration impossibilities."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-CHK-04", ctx, _drive_temporal_consistency)


CHECK_DIRECTION_DRIVERS: Final[dict[str, type[CapabilityDriver]]] = {
    "CAP-CHK-01": ConsistencyCheckDriver,
    "CAP-CHK-02": SeriesConsistencyDriver,
    "CAP-CHK-03": SeriesVoiceDriftDriver,
    "CAP-CHK-04": TemporalConsistencyDriver,
    "CAP-CHK-05": VoiceCheckDriver,
    "CAP-CHK-06": VoiceDriftDriver,
    "CAP-CHK-07": AuthorVoiceDriftDriver,
}
"""cap_id → driver class for the whole ``check`` direction (registry-mirrored)."""
