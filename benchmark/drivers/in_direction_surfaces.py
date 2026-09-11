"""IN-direction capability drivers, beyond-KB surfaces (CAP-IN-05..09).

The five IN drivers whose endpoints live outside the core KB routes
(``benchmark.drivers.in_direction`` holds the KB-surface half plus the
direction's registration facade):

- CAP-IN-05 ``ManualAuthoringDriver`` — manual entry authoring (novel
  overlay + optional series canon + optional relationship, gated on
  ``ctx.targets``).
- CAP-IN-06 ``ScopeMoveDriver`` — series join preview/apply, promote,
  demote (series lifecycle prerequisite, map §7).
- CAP-IN-07 ``TimelineExtractionDriver`` — SSE flavor A stream +
  first-item confirmation.
- CAP-IN-08 ``WikiRefreshDriver`` — summary refresh + mark-stale.
- CAP-IN-09 ``CharacterVoiceDriver`` — SSE flavor B per-character voice
  results.

Failure/typing contract: see ``benchmark.drivers.in_parsing``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.drivers.in_parsing import (
    as_bool,
    as_float,
    as_int,
    as_list,
    as_opt_text,
    as_str_tuple,
    as_text,
    check_terminal,
    guarded,
    require_target,
    response_field,
)
from benchmark.drivers.in_records import (
    CharacterVoiceRecord,
    EntryRef,
    ExtractedExpression,
    ManualAuthoringRecord,
    RelationshipRef,
    ScopeMoveRecord,
    TimelineExtractionRecord,
    VoiceProfile,
    WikiRefreshRecord,
)
from benchmark.drivers.shapes import invoke_rest, invoke_sse
from benchmark.sse import SseItem, SseProgress, SseResult

if TYPE_CHECKING:
    from benchmark.drivers.base import CapabilityContext, CapabilityResult

JOIN_POSITION: Final[int] = 1
"""1-based series slot used for the join apply (first member)."""

AUTHORING_NAME: Final[str] = "Benchmark Figur"
AUTHORING_ENTITY_TYPE: Final[str] = "character"
AUTHORING_REL_TYPE: Final[str] = "related_to"
AUTHORING_UPDATE: Final[str] = "Manuell aktualisiert."


# ---------------------------------------------------------------------------
# CAP-IN-05 — ManualAuthoringDriver: entries (novel + series) + relationship
# ---------------------------------------------------------------------------


def _authoring_body() -> dict[str, object]:
    return {
        "entity_type": AUTHORING_ENTITY_TYPE,
        "name": AUTHORING_NAME,
        "body": "Manuell angelegt.",
        "source": "benchmark",
    }


def _entry_ref(body: object) -> EntryRef:
    """``KBEntryResponse``/``SeriesKBEntry`` identity triple."""
    return EntryRef(
        id=as_text(response_field(body, "id")),
        name=as_text(response_field(body, "name")),
        entity_type=as_text(response_field(body, "entity_type")),
    )


def _author_series_entry(ctx: CapabilityContext) -> EntryRef | None:
    series_id = ctx.targets.get("series_id")
    if series_id is None:
        return None
    base = f"/api/v1/series/{series_id}/kb"
    created = invoke_rest(
        ctx,
        step="CAP-IN-05:create-series-entry",
        method="POST",
        path=base,
        json_body=_authoring_body(),
    )
    entry_id = as_text(response_field(created, "id"))
    updated = invoke_rest(
        ctx,
        step="CAP-IN-05:update-series-entry",
        method="PATCH",
        path=f"{base}/{entry_id}",
        json_body={"body": AUTHORING_UPDATE},
    )
    return _entry_ref(updated)


def _author_relationship(ctx: CapabilityContext, entry_id: str) -> RelationshipRef | None:
    target_id = ctx.targets.get("entry_id")
    if target_id is None:
        return None
    rel = invoke_rest(
        ctx,
        step="CAP-IN-05:create-relationship",
        method="POST",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/relationships",
        json_body={"source_id": entry_id, "target_id": target_id, "rel_type": AUTHORING_REL_TYPE},
    )
    return RelationshipRef(
        id=as_text(response_field(rel, "id")),
        rel_type=as_text(response_field(rel, "rel_type")),
        source_id=as_text(response_field(rel, "source_id")),
        target_id=as_text(response_field(rel, "target_id")),
    )


def _drive_manual_authoring(ctx: CapabilityContext) -> ManualAuthoringRecord:
    base = f"/api/v1/novels/{ctx.novel_id}/kb/entries"
    created = invoke_rest(
        ctx,
        step="CAP-IN-05:create-novel-entry",
        method="POST",
        path=base,
        json_body=_authoring_body(),
    )
    entry_id = as_text(response_field(created, "id"))
    updated = invoke_rest(
        ctx,
        step="CAP-IN-05:update-novel-entry",
        method="PATCH",
        path=f"{base}/{entry_id}",
        json_body={"body": AUTHORING_UPDATE},
    )
    return ManualAuthoringRecord(
        novel_entry=_entry_ref(updated),
        series_entry=_author_series_entry(ctx),
        relationship=_author_relationship(ctx, entry_id),
    )


class ManualAuthoringDriver:
    """CAP-IN-05 — manual entry authoring; series/rel parts when targeted."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-IN-05", ctx, _drive_manual_authoring)


# ---------------------------------------------------------------------------
# CAP-IN-06 — ScopeMoveDriver: join preview/apply, promote, demote
# ---------------------------------------------------------------------------


def _drive_scope_move(ctx: CapabilityContext) -> ScopeMoveRecord:
    series_id = require_target(ctx, "series_id")
    preview = invoke_rest(
        ctx,
        step="CAP-IN-06:join-preview",
        method="POST",
        path=f"/api/v1/series/{series_id}/novels",
        json_body={"novel_id": ctx.novel_id},
    )
    joined = invoke_rest(
        ctx,
        step="CAP-IN-06:join-apply",
        method="POST",
        path=f"/api/v1/series/{series_id}/novels/{ctx.novel_id}/apply",
        json_body={"position": JOIN_POSITION},
    )
    entry_id = require_target(ctx, "entry_id")
    promoted = invoke_rest(
        ctx,
        step="CAP-IN-06:promote",
        method="POST",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/{entry_id}/promote",
    )
    demoted = invoke_rest(
        ctx,
        step="CAP-IN-06:demote",
        method="POST",
        path=f"/api/v1/novels/{ctx.novel_id}/kb/{entry_id}/demote",
        json_body={"series_id": series_id},
    )
    return ScopeMoveRecord(
        series_id=series_id,
        canon_empty=as_bool(response_field(preview, "canon_empty")),
        treatment_count=len(as_list(response_field(preview, "treatments"), "treatment list")),
        join_position=as_int(response_field(joined, "position")),
        promoted_count=as_int(response_field(joined, "promoted_to_canon")),
        entry_id=entry_id,
        promoted_scope=as_text(response_field(promoted, "scope")),
        demoted_scope=as_text(response_field(demoted, "scope")),
    )


class ScopeMoveDriver:
    """CAP-IN-06 — scope moves; requires ``targets['series_id']`` (map §7)."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-IN-06", ctx, _drive_scope_move)


# ---------------------------------------------------------------------------
# CAP-IN-07 — TimelineExtractionDriver: SSE flavor A + confirm (map §6)
# ---------------------------------------------------------------------------


def _drive_timeline(ctx: CapabilityContext) -> TimelineExtractionRecord:
    extract_path = f"/api/v1/planning/timeline/{ctx.novel_id}/extract"
    stream = invoke_sse(
        ctx,
        step="CAP-IN-07:extract",
        path=extract_path,
        json_body={"chapter_ids": sorted(ctx.chapter_ids.values())},
    )
    check_terminal(stream.terminal, "CAP-IN-07")
    expressions = tuple(
        ExtractedExpression(
            id=as_text(response_field(item.payload, "id")),
            expression=as_text(response_field(item.payload, "expression")),
            event_name=as_text(response_field(item.payload, "event_name")),
            timestamp_raw=as_text(response_field(item.payload, "timestamp_raw")),
            chapter_reference=as_text(response_field(item.payload, "chapter_reference")),
            character_names=as_str_tuple(response_field(item.payload, "character_names")),
            location_name=as_text(response_field(item.payload, "location_name")),
            confidence=as_float(response_field(item.payload, "confidence")),
            context=as_text(response_field(item.payload, "context")),
        )
        for item in stream.events
        if isinstance(item, SseItem)
    )
    confirmed_id: str | None = None
    confirmed_name: str | None = None
    if expressions:
        first = expressions[0]
        confirmed = invoke_rest(
            ctx,
            step="CAP-IN-07:confirm",
            method="POST",
            path=f"{extract_path}/confirm",
            json_body={
                "expression": first.expression,
                "event_name": first.event_name,
                "timestamp_raw": first.timestamp_raw,
                "chapter_reference": first.chapter_reference,
                "character_names": list(first.character_names),
                "location_name": first.location_name,
                "confidence": first.confidence,
                "context": first.context,
            },
        )
        confirmed_id = as_text(response_field(confirmed, "id"))
        confirmed_name = as_text(response_field(confirmed, "event_name"))
    return TimelineExtractionRecord(
        expressions=expressions,
        confirmed_event_id=confirmed_id,
        confirmed_event_name=confirmed_name,
    )


class TimelineExtractionDriver:
    """CAP-IN-07 — timeline expression stream + first-item confirmation."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-IN-07", ctx, _drive_timeline)


# ---------------------------------------------------------------------------
# CAP-IN-08 — WikiRefreshDriver: refresh one entity, then mark-stale
# ---------------------------------------------------------------------------


def _drive_wiki_refresh(ctx: CapabilityContext) -> WikiRefreshRecord:
    entry_id = require_target(ctx, "entry_id")
    refreshed = invoke_rest(
        ctx,
        step="CAP-IN-08:refresh",
        method="POST",
        path=f"/api/v1/novels/{ctx.novel_id}/wiki/summaries/{entry_id}/refresh",
        json_body={"force": True},
    )
    stale = invoke_rest(
        ctx,
        step="CAP-IN-08:mark-stale",
        method="POST",
        path=f"/api/v1/novels/{ctx.novel_id}/wiki/mark-stale",
        json_body={"prompt_version": None},
    )
    return WikiRefreshRecord(
        summary_id=as_opt_text(response_field(refreshed, "summary_id")),
        status=as_text(response_field(refreshed, "status")),
        message=as_text(response_field(refreshed, "message")),
        affected_count=as_int(response_field(stale, "affected_count")),
    )


class WikiRefreshDriver:
    """CAP-IN-08 — wiki refresh + mark-stale on ``targets['entry_id']``."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-IN-08", ctx, _drive_wiki_refresh)


# ---------------------------------------------------------------------------
# CAP-IN-09 — CharacterVoiceDriver: SSE flavor B (map §6)
# ---------------------------------------------------------------------------


def _voice_profile(envelope: object) -> VoiceProfile:
    """One flavor-B ``result`` payload (``CharacterVoiceResult``)."""
    result = response_field(envelope, "result")
    return VoiceProfile(
        character_name=as_text(response_field(result, "character_name")),
        kb_entry_id=as_opt_text(response_field(result, "kb_entry_id")),
        has_voice_analysis=response_field(result, "voice_analysis") is not None,
        distinctiveness_notes=as_opt_text(response_field(result, "distinctiveness_notes")),
    )


def _drive_character_voice(ctx: CapabilityContext) -> CharacterVoiceRecord:
    stream = invoke_sse(
        ctx,
        step="CAP-IN-09",
        path=f"/api/v1/analysis/character-voice/{ctx.novel_id}",
        json_body={"chapter_ids": None},
    )
    check_terminal(stream.terminal, "CAP-IN-09")
    return CharacterVoiceRecord(
        characters=tuple(
            _voice_profile(item.payload) for item in stream.events if isinstance(item, SseResult)
        ),
        progress_messages=tuple(
            as_text(response_field(item.payload, "progress"))
            for item in stream.events
            if isinstance(item, SseProgress)
        ),
    )


class CharacterVoiceDriver:
    """CAP-IN-09 — character-voice stream B; results carry ``kb_entry_id``."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-IN-09", ctx, _drive_character_voice)
