"""CHECK-direction series-scope drivers (CAP-CHK-02/03, plan Task 10).

The two REST check drivers whose endpoints live on the series routes
(``benchmark.drivers.check_direction`` holds the novel-surface half plus
the direction's registration facade; ``benchmark.drivers.check_direction_streams``
holds the SSE half):

- CAP-CHK-02 ``SeriesConsistencyDriver`` — checks the run's novel (band)
  prose against the series Canon KB, then reads back the persisted
  store-on-run (C2) drift snapshot.
- CAP-CHK-03 ``SeriesVoiceDriftDriver`` — checks the band's narrator
  drift against the series voice baseline; graceful ``no_profile`` when
  the series voice cannot be analysed.

Structural requirement (router-verified, ``series/router_consistency.py``
+ ``series/router_voice_drift.py``): both endpoints take ``series_id`` as
the path parameter and the service verifies the novel's membership
(anti-enumeration — a non-member novel surfaces as 403). A run therefore
drives them only when the series lifecycle prerequisite (map §7) gave it
a joined series: missing ``targets['series_id']`` →
``SKIPPED(structural)``, never a fabricated id. Everything else degrades
gracefully server-side (empty canon → ``canon_entry_count=0`` no-op;
missing series voice profile → ``no_profile``), so no further structural
gate exists.

The shared drift-payload parsers (``TrendPoint``/``JumpPoint``/
``VoiceDriftResult``/``AuthorVoiceDriftResult`` projections) live here —
CAP-CHK-06/07 in ``check_direction_streams`` reuse them.
Failure/typing contract: see ``benchmark.drivers.in_parsing``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.drivers.check_records import (
    AuthorDriftResult,
    CanonConflictFinding,
    DriftVerdict,
    JumpPointRef,
    SeriesConsistencyRecord,
    SeriesVoiceDriftRecord,
    SnapshotRead,
    TrendPointRef,
)
from benchmark.drivers.in_parsing import (
    as_float,
    as_int,
    as_list,
    as_opt_float,
    as_opt_object,
    as_opt_text,
    as_str_tuple,
    as_text,
    guarded,
    require_target,
    response_field,
)
from benchmark.drivers.shapes import invoke_rest

if TYPE_CHECKING:
    from benchmark.drivers.base import CapabilityContext, CapabilityResult

SERIES_BASE: Final[str] = "/api/v1/series"


# ---------------------------------------------------------------------------
# Shared drift-payload parsers (reused by check_direction_streams)
# ---------------------------------------------------------------------------


def _count_pairs(raw: object) -> tuple[tuple[str, float], ...]:
    """``dict[str, float]`` → key-sorted tuple pairs (deterministic equality)."""
    deltas = as_opt_object(raw)
    if deltas is None:
        return ()
    return tuple(sorted((as_text(key), as_float(value)) for key, value in deltas.items()))


def trend_point(body: object) -> TrendPointRef:
    """``TrendPoint`` (core ``voice_drift_scoring_types``) — complete."""
    return TrendPointRef(
        chapter_id=as_text(response_field(body, "chapter_id")),
        match_subscore=as_float(response_field(body, "match_subscore")),
        per_metric_deltas=_count_pairs(response_field(body, "per_metric_deltas")),
        band=as_text(response_field(body, "band")),
    )


def jump_point(body: object) -> JumpPointRef:
    """``JumpPoint`` (core ``voice_drift_scoring_types``) — complete."""
    return JumpPointRef(
        from_chapter_id=as_text(response_field(body, "from_chapter_id")),
        to_chapter_id=as_text(response_field(body, "to_chapter_id")),
        jumped_metrics=as_str_tuple(response_field(body, "jumped_metrics")),
        magnitude=as_float(response_field(body, "magnitude")),
    )


def drift_verdict(body: object) -> DriftVerdict:
    """``VoiceDriftResult`` (core ``character_voice_drift_types``) — complete."""
    return DriftVerdict(
        drift_type=as_text(response_field(body, "drift_type")),
        confidence=as_float(response_field(body, "confidence")),
        longitudinal_reasons=as_str_tuple(response_field(body, "longitudinal_reasons")),
        per_chapter_notes=tuple(
            (
                as_text(response_field(note, "chapter_id")),
                as_text(response_field(note, "note")),
            )
            for note in as_list(response_field(body, "per_chapter_notes"), "note list")
        ),
        suggested_attention=as_str_tuple(response_field(body, "suggested_attention")),
    )


def author_drift_result(body: object) -> AuthorDriftResult:
    """``AuthorVoiceDriftResult`` (``analysis/schemas_author_voice_drift``)."""
    return AuthorDriftResult(
        novel_id=as_text(response_field(body, "novel_id")),
        trend=tuple(
            trend_point(point) for point in as_list(response_field(body, "trend"), "trend list")
        ),
        jumps=tuple(
            jump_point(point) for point in as_list(response_field(body, "jumps"), "jump list")
        ),
        overall_match_score=as_opt_float(response_field(body, "overall_match_score")),
        overall_band=as_opt_text(response_field(body, "overall_band")),
        drift=drift_verdict(response_field(body, "drift")),
    )


def author_drift_response(body: object) -> tuple[AuthorDriftResult | None, str | None]:
    """Split ``AuthorVoiceDriftResponse`` into (result, no_profile_reason)."""
    raw_result = response_field(body, "result")
    result = author_drift_result(raw_result) if raw_result is not None else None
    raw_no_profile = response_field(body, "no_profile")
    no_profile_reason = (
        as_text(response_field(raw_no_profile, "reason")) if raw_no_profile is not None else None
    )
    return result, no_profile_reason


# ---------------------------------------------------------------------------
# CAP-CHK-02 — SeriesConsistencyDriver: canon check + snapshot read-back
# ---------------------------------------------------------------------------


def _canon_conflict(body: object) -> CanonConflictFinding:
    """``CanonConflict`` (core ``series_consistency_types``) — complete."""
    return CanonConflictFinding(
        canon_entry_slug=as_text(response_field(body, "canon_entry_slug")),
        canon_entry_name=as_text(response_field(body, "canon_entry_name")),
        chapter_text_excerpt=as_text(response_field(body, "chapter_text_excerpt")),
        canon_statement=as_text(response_field(body, "canon_statement")),
        explanation=as_text(response_field(body, "explanation")),
        severity=as_text(response_field(body, "severity")),
    )


def _snapshot_read(body: object) -> SnapshotRead:
    """Persistence projection of ``SeriesDriftSnapshotResponse`` (docstring)."""
    return SnapshotRead(
        generated_at=as_opt_text(response_field(body, "generated_at")),
        stale=bool(response_field(body, "stale")),
        has_consistency=response_field(body, "consistency") is not None,
        has_voice_drift=response_field(body, "voice_drift") is not None,
    )


def _drive_series_consistency(ctx: CapabilityContext) -> SeriesConsistencyRecord:
    series_id = require_target(ctx, "series_id")
    check_path = f"{SERIES_BASE}/{series_id}/consistency/check"
    checked = invoke_rest(
        ctx,
        step="CAP-CHK-02:check",
        method="POST",
        path=check_path,
        json_body={"novel_id": ctx.novel_id},
    )
    conflicts = tuple(
        _canon_conflict(conflict)
        for conflict in as_list(response_field(checked, "conflicts"), "conflict list")
    )
    snapshot = invoke_rest(
        ctx,
        step="CAP-CHK-02:snapshot",
        method="GET",
        path=f"{SERIES_BASE}/{series_id}/consistency/{ctx.novel_id}",
    )
    return SeriesConsistencyRecord(
        series_id=as_text(response_field(checked, "series_id")),
        novel_id=as_text(response_field(checked, "novel_id")),
        conflicts=conflicts,
        summary=as_text(response_field(checked, "summary")),
        canon_entry_count=as_int(response_field(checked, "canon_entry_count")),
        chapter_count=as_int(response_field(checked, "chapter_count")),
        snapshot=_snapshot_read(snapshot),
    )


class SeriesConsistencyDriver:
    """CAP-CHK-02 — prose vs series Canon + snapshot read-back."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-CHK-02", ctx, _drive_series_consistency)


# ---------------------------------------------------------------------------
# CAP-CHK-03 — SeriesVoiceDriftDriver: series narrator drift vs baseline
# ---------------------------------------------------------------------------


def _drive_series_voice_drift(ctx: CapabilityContext) -> SeriesVoiceDriftRecord:
    series_id = require_target(ctx, "series_id")
    response = invoke_rest(
        ctx,
        step="CAP-CHK-03",
        method="POST",
        path=f"{SERIES_BASE}/{series_id}/voice-drift/check",
        json_body={"novel_id": ctx.novel_id, "chapter_ids": None},
    )
    result, no_profile_reason = author_drift_response(response)
    return SeriesVoiceDriftRecord(
        series_id=series_id,
        novel_id=as_text(response_field(response, "novel_id")),
        result=result,
        no_profile_reason=no_profile_reason,
    )


class SeriesVoiceDriftDriver:
    """CAP-CHK-03 — series narrator drift; graceful ``no_profile``."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-CHK-03", ctx, _drive_series_voice_drift)
