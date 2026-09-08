"""IN-direction driver, entity resolution (CAP-IN-10, ADR-085 P6).

``ResolutionDriver`` drives the mounted detection surface on the run's
novel scope (plan Task 14): ``POST /kb/resolution/analyze`` with
``{"refresh": false}`` (cache-coherent — the metrics score the
deterministic core, spec §8), parsed into the typed records of
``benchmark.drivers.in_records`` and recorded to the run sink; then it
endorses EVERY surfaced suggestion (merge measurement: endorse all
non-rejected suggestions — spec §8; nothing is rejected in a clean run,
so the reject endpoint is deliberately not driven and stays
registry-pinned). Each endorse result is recorded — raw exchange via the
shape helper, parsed outcome on the returned record. The survivor is
never overridden: the endorse body is omitted so the server's §6.1
deterministic total order picks it.

Failure/typing contract: see ``benchmark.drivers.in_parsing``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmark.drivers.in_parsing import (
    as_bool,
    as_float,
    as_int,
    as_list,
    as_str_tuple,
    as_text,
    guarded,
    response_field,
)
from benchmark.drivers.in_records import (
    BandStats,
    MergeResult,
    ResolutionRecord,
    ResolutionSuggestion,
)
from benchmark.drivers.shapes import invoke_rest

if TYPE_CHECKING:
    from benchmark.drivers.base import CapabilityContext, CapabilityResult

__all__ = ["ResolutionDriver"]


def _suggestion(item: object) -> ResolutionSuggestion:
    """One surfaced merge suggestion (``SuggestionResponse``, spec §7)."""
    return ResolutionSuggestion(
        suggestion_id=as_text(response_field(item, "suggestion_id")),
        entry_a_id=as_text(response_field(item, "entry_a_id")),
        entry_b_id=as_text(response_field(item, "entry_b_id")),
        name_a=as_text(response_field(item, "name_a")),
        name_b=as_text(response_field(item, "name_b")),
        confidence=as_float(response_field(item, "confidence")),
        band=as_text(response_field(item, "band")),
        auto_merge_eligible=as_bool(response_field(item, "auto_merge_eligible")),
    )


def _merge_result(body: object) -> MergeResult:
    """One executed merge (``MergeExecutionResult``, spec §6)."""
    return MergeResult(
        survivor_id=as_text(response_field(body, "survivor_id")),
        loser_id=as_text(response_field(body, "loser_id")),
        merged_fact_keys=as_str_tuple(response_field(body, "merged_fact_keys")),
        repointed_relationships=as_int(response_field(body, "repointed_relationships")),
        skipped_relationships=as_int(response_field(body, "skipped_relationships")),
    )


def _endorse(ctx: CapabilityContext, base: str, suggestion: ResolutionSuggestion) -> MergeResult:
    """``POST .../suggestions/{id}/endorse`` — one result per suggestion."""
    merged = invoke_rest(
        ctx,
        step="CAP-IN-10:endorse",
        method="POST",
        path=f"{base}/suggestions/{suggestion.suggestion_id}/endorse",
    )
    return _merge_result(merged)


def _drive_resolution(ctx: CapabilityContext) -> ResolutionRecord:
    base = f"/api/v1/novels/{ctx.novel_id}/kb/resolution"
    analysis = invoke_rest(
        ctx,
        step="CAP-IN-10:analyze",
        method="POST",
        path=f"{base}/analyze",
        json_body={"refresh": False},
    )
    suggestions = tuple(
        _suggestion(item)
        for item in as_list(response_field(analysis, "suggestions"), "suggestion list")
    )
    stats = response_field(analysis, "stats")
    merges = tuple(_endorse(ctx, base, suggestion) for suggestion in suggestions)
    return ResolutionRecord(
        suggestions=suggestions,
        stats=BandStats(
            review=as_int(response_field(stats, "review")),
            auto_eligible=as_int(response_field(stats, "auto_eligible")),
            suppressed=as_int(response_field(stats, "suppressed")),
        ),
        cache_hit=as_bool(response_field(analysis, "cache_hit")),
        merges=merges,
    )


class ResolutionDriver:
    """CAP-IN-10 — duplicate detection + endorse-all merge measurement."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-IN-10", ctx, _drive_resolution)
