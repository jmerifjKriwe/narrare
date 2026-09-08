"""IN-direction capability drivers, KB surface (CAP-IN-01..04, plan Task 8).

This module owns the four drivers on the core KB routes
(``/novels/{novel_id}/kb/...``): extraction (01), assist session (02),
improve (03), worldbuilding (04). The remaining IN drivers live in
their own RULE-04 modules — beyond-KB surfaces (05..09) in
``benchmark.drivers.in_direction_surfaces``, entity resolution (10) in
``benchmark.drivers.in_resolution``; THIS module is the direction's
registration facade — ``IN_DIRECTION_DRIVERS`` (the cap_id → driver
class map wired into ``benchmark.drivers``) is assembled here from all
three halves (facade precedent: ``benchmark.capabilities``).

Shared rules (module docstring of ``benchmark.drivers.in_parsing``):
every driver invokes exactly its registry ``EndpointSpec`` surface via
the shape helpers, parses responses into the typed records of
``benchmark.drivers.in_records``, and returns a ``CapabilityResult``
whose ``parsed`` carries that record; raw exchanges flow to the run
sink. A missing ingest-discovered target → ``SKIPPED(structural)``;
transport/HTTP/SSE/shape failures → ``ERROR`` with a reason.

Dual use (CAP-IN-01): extraction is ALREADY driven during the build path
by ``benchmark.ingest`` (plan Task 6, per-chapter cycle). ``ExtractionDriver``
exists for POST-BUILD re-invocation on one target chapter — the same
production surface (extract → endorse-all → apply), deliberately scoped
to a single chapter instead of the whole novel.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.drivers.in_direction_surfaces import (
    CharacterVoiceDriver,
    ManualAuthoringDriver,
    ScopeMoveDriver,
    TimelineExtractionDriver,
    WikiRefreshDriver,
)
from benchmark.drivers.in_parsing import (
    as_bool,
    as_float,
    as_int,
    as_list,
    as_opt_object,
    as_opt_text,
    as_text,
    guarded,
    require_target,
    response_field,
)
from benchmark.drivers.in_records import (
    AssistSessionRecord,
    ExtractionCandidate,
    ExtractionRecord,
    ImproveRecord,
    WorldbuildingRecord,
)
from benchmark.drivers.in_resolution import ResolutionDriver
from benchmark.drivers.shapes import invoke_rest

if TYPE_CHECKING:
    from benchmark.drivers.base import CapabilityContext, CapabilityDriver, CapabilityResult

ASSIST_ENTITY_TYPE: Final[str] = "character"
"""Session entity type (deterministic; corpus reference persons → character)."""

ASSIST_FIELD_KEY: Final[str] = "name"
"""Session field answered/patched — required before completion (session model)."""

ASSIST_NAME: Final[str] = "Benchmark Figur"
"""Deterministic session name value (corpus-language data, not code)."""

__all__ = [
    "ASSIST_ENTITY_TYPE",
    "ASSIST_FIELD_KEY",
    "ASSIST_NAME",
    "IN_DIRECTION_DRIVERS",
    "AssistSessionDriver",
    "CharacterVoiceDriver",
    "ExtractionDriver",
    "ImproveAnalysisDriver",
    "ManualAuthoringDriver",
    "ResolutionDriver",
    "ScopeMoveDriver",
    "TimelineExtractionDriver",
    "WikiRefreshDriver",
    "WorldbuildingDriver",
]


# ---------------------------------------------------------------------------
# CAP-IN-01 — ExtractionDriver (post-build re-invocation; build path = ingest)
# ---------------------------------------------------------------------------


def _candidate(item: object) -> ExtractionCandidate:
    """One ``ExtractionItem`` (packages/core extraction_types, map §4.3.1)."""
    return ExtractionCandidate(
        item_type=as_text(response_field(item, "item_type")),
        name=as_text(response_field(item, "name")),
        confidence=as_float(response_field(item, "confidence")),
        source_text=as_text(response_field(item, "source_text")),
        entity_type=as_opt_text(response_field(item, "entity_type")),
        proposed_content=as_opt_object(response_field(item, "proposed_content")),
        target_entity_id=as_opt_text(response_field(item, "target_entity_id")),
        relationship_type=as_opt_text(response_field(item, "relationship_type")),
        related_entity_name=as_opt_text(response_field(item, "related_entity_name")),
        conflict_description=as_opt_text(response_field(item, "conflict_description")),
    )


def _apply_item(candidate: ExtractionCandidate) -> dict[str, object]:
    """Endorse-all mapping: ``ApplyExtractionItem`` has no confidence field."""
    return {
        "item_type": candidate.item_type,
        "name": candidate.name,
        "entity_type": candidate.entity_type,
        "proposed_content": candidate.proposed_content,
        "target_entity_id": candidate.target_entity_id,
        "relationship_type": candidate.relationship_type,
        "related_entity_name": candidate.related_entity_name,
        "source_text": candidate.source_text,
    }


def _drive_extraction(ctx: CapabilityContext) -> ExtractionRecord:
    chapter_id = require_target(ctx, "chapter_id")
    body = invoke_rest(
        ctx,
        step="CAP-IN-01:extract",
        method="POST",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/extract/{chapter_id}",
    )
    candidates = tuple(
        _candidate(item) for item in as_list(response_field(body, "results"), "candidate list")
    )
    applied = invoke_rest(
        ctx,
        step="CAP-IN-01:apply",
        method="POST",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/extract/apply",
        json_body={"items": [_apply_item(candidate) for candidate in candidates]},
    )
    return ExtractionRecord(
        chapter_id=chapter_id,
        candidates=candidates,
        analysis_notes=as_text(response_field(body, "analysis_notes")),
        created=tuple(
            as_text(response_field(entry, "id"))
            for entry in as_list(response_field(applied, "created_entries"), "entry list")
        ),
        updated=tuple(
            as_text(response_field(entry, "id"))
            for entry in as_list(response_field(applied, "updated_entries"), "entry list")
        ),
    )


class ExtractionDriver:
    """CAP-IN-01 — post-build re-extraction on ``targets['chapter_id']``."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-IN-01", ctx, _drive_extraction)


# ---------------------------------------------------------------------------
# CAP-IN-02 — AssistSessionDriver: full six-step session lifecycle
# ---------------------------------------------------------------------------


def _drive_assist_session(ctx: CapabilityContext) -> AssistSessionRecord:
    base = f"/api/v1/novels/{ctx.novel_id}/kb/sessions"
    session = invoke_rest(
        ctx,
        step="CAP-IN-02:step-1",
        method="POST",
        path=base,
        json_body={"entity_type": ASSIST_ENTITY_TYPE},
    )
    session_id = as_text(response_field(session, "id"))
    invoke_rest(
        ctx,
        step="CAP-IN-02:step-2",
        method="POST",
        path=f"{base}/{session_id}/suggest/{ASSIST_FIELD_KEY}",
    )
    invoke_rest(ctx, step="CAP-IN-02:step-3", method="POST", path=f"{base}/{session_id}/interview")
    invoke_rest(ctx, step="CAP-IN-02:step-4", method="POST", path=f"{base}/{session_id}/enhance")
    invoke_rest(
        ctx,
        step="CAP-IN-02:step-5",
        method="PATCH",
        path=f"{base}/{session_id}/fields/{ASSIST_FIELD_KEY}",
        json_body={"value": ASSIST_NAME},
    )
    completed = invoke_rest(
        ctx, step="CAP-IN-02:step-6", method="POST", path=f"{base}/{session_id}/complete"
    )
    return AssistSessionRecord(
        session_id=session_id,
        entity_type=as_text(response_field(session, "entity_type")),
        status=as_text(response_field(response_field(completed, "session"), "status")),
        entry_id=as_text(response_field(completed, "entry_id")),
    )


class AssistSessionDriver:
    """CAP-IN-02 — assisted creation session: create→suggest→…→complete."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-IN-02", ctx, _drive_assist_session)


# ---------------------------------------------------------------------------
# CAP-IN-03 — ImproveAnalysisDriver: analyze then apply every suggestion
# ---------------------------------------------------------------------------


def _drive_improve(ctx: CapabilityContext) -> ImproveRecord:
    entry_id = require_target(ctx, "entry_id")
    base = f"/api/v1/novels/{ctx.novel_id}/kb/entities/{entry_id}/improve"
    analysis = invoke_rest(ctx, step="CAP-IN-03:analyze", method="POST", path=base)
    suggestion_ids = [
        as_int(response_field(suggestion, "suggestion_id"))
        for suggestion in as_list(response_field(analysis, "suggestions"), "suggestion list")
    ]
    applied = invoke_rest(
        ctx,
        step="CAP-IN-03:apply",
        method="POST",
        path=f"{base}/apply",
        json_body={"suggestion_ids": suggestion_ids},
    )
    return ImproveRecord(
        entry_id=entry_id,
        suggestion_count=len(suggestion_ids),
        completeness_score=as_float(response_field(analysis, "completeness_score")),
        overall_assessment=as_text(response_field(analysis, "overall_assessment")),
        applied_count=as_int(response_field(applied, "applied_count")),
        apply_success=as_bool(response_field(applied, "success")),
        apply_message=as_text(response_field(applied, "message")),
    )


class ImproveAnalysisDriver:
    """CAP-IN-03 — improve analysis + apply on ``targets['entry_id']``."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-IN-03", ctx, _drive_improve)


# ---------------------------------------------------------------------------
# CAP-IN-04 — WorldbuildingDriver: analyze then apply connection suggestions
# ---------------------------------------------------------------------------


def _drive_worldbuilding(ctx: CapabilityContext) -> WorldbuildingRecord:
    base = f"/api/v1/novels/{ctx.novel_id}/kb/worldbuilding"
    analysis = invoke_rest(
        ctx, step="CAP-IN-04:analyze", method="POST", path=f"{base}/analyze", json_body={}
    )
    indices = [
        as_int(response_field(suggestion, "finding_index"))
        for suggestion in as_list(
            response_field(analysis, "connection_suggestions"), "suggestion list"
        )
    ]
    applied = invoke_rest(
        ctx,
        step="CAP-IN-04:apply",
        method="POST",
        path=f"{base}/apply",
        json_body={"finding_indices": indices, "analysis": analysis},
    )
    return WorldbuildingRecord(
        gap_count=len(as_list(response_field(analysis, "gap_findings"), "finding list")),
        connection_count=len(indices),
        consistency_count=len(
            as_list(response_field(analysis, "consistency_issues"), "issue list")
        ),
        worldbuilding_score=as_float(response_field(analysis, "worldbuilding_score")),
        applied_indices=tuple(indices),
        created_count=as_int(response_field(applied, "created_count")),
        failed_count=as_int(response_field(applied, "failed_count")),
    )


class WorldbuildingDriver:
    """CAP-IN-04 — worldbuilding analyze/apply over the run's novel."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-IN-04", ctx, _drive_worldbuilding)


IN_DIRECTION_DRIVERS: Final[dict[str, type[CapabilityDriver]]] = {
    "CAP-IN-01": ExtractionDriver,
    "CAP-IN-02": AssistSessionDriver,
    "CAP-IN-03": ImproveAnalysisDriver,
    "CAP-IN-04": WorldbuildingDriver,
    "CAP-IN-05": ManualAuthoringDriver,
    "CAP-IN-06": ScopeMoveDriver,
    "CAP-IN-07": TimelineExtractionDriver,
    "CAP-IN-08": WikiRefreshDriver,
    "CAP-IN-09": CharacterVoiceDriver,
    "CAP-IN-10": ResolutionDriver,
}
"""cap_id → driver class for the whole ``in`` direction (registry-mirrored)."""
