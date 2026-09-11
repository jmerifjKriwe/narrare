"""OUT-direction capability drivers, scope/content read surfaces (CAP-OUT-05..07).

The three OUT drivers that read KB content across scopes and derived
surfaces (``benchmark.drivers.out_direction`` holds the KB-surface half
plus the direction's registration facade;
``benchmark.drivers.out_direction_assist`` holds the authoring-assist
surfaces 08-10 and the shared retrieval probe):

- CAP-OUT-05 ``SeriesCanonReadDriver`` — series-canon list + single
  read-back (requires ``targets['series_id']``).
- CAP-OUT-06 ``WikiReadDriver`` — index health, summaries (prose is
  recorded-not-scored per plan Task 13), chapter summary.
- CAP-OUT-07 ``TimelineReadDriver`` — event list (NOT paginated —
  plain list response), single read-back, character-age report.

Failure/typing contract: see ``benchmark.drivers.in_parsing`` (the
strict accessors + ``guarded`` are the driver-framework plumbing,
shared by both directions). All ten OUT entries are REST-shaped
(registry-verified) — this direction never opens SSE streams.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.drivers.in_parsing import (
    as_bool,
    as_int,
    as_list,
    as_opt_float,
    as_opt_text,
    as_text,
    guarded,
    require_target,
    response_field,
)
from benchmark.drivers.out_records import (
    CanonEntryRef,
    CanonReadRecord,
    CharacterAge,
    TimelineEventRef,
    TimelineReadRecord,
    WikiReadRecord,
    WikiSummaryProse,
)
from benchmark.drivers.shapes import invoke_rest

if TYPE_CHECKING:
    from benchmark.drivers.base import CapabilityContext, CapabilityDriver, CapabilityResult


# ---------------------------------------------------------------------------
# CAP-OUT-05 — SeriesCanonReadDriver: canon list + first-entry read-back
# ---------------------------------------------------------------------------


def _canon_entry(body: object) -> CanonEntryRef:
    """``SeriesKBEntry`` identity (Core schema; ``scope`` literal)."""
    return CanonEntryRef(
        id=as_text(response_field(body, "id")),
        name=as_text(response_field(body, "name")),
        entity_type=as_text(response_field(body, "entity_type")),
        slug=as_text(response_field(body, "slug")),
        scope=as_text(response_field(body, "scope")),
    )


def _drive_series_canon(ctx: CapabilityContext) -> CanonReadRecord:
    series_id = require_target(ctx, "series_id")
    base = f"/api/v1/series/{series_id}/kb"
    listed = invoke_rest(ctx, step="CAP-OUT-05:list", method="GET", path=base)
    entries = tuple(_canon_entry(entry) for entry in as_list(listed, "canon entry list"))
    single: CanonEntryRef | None = None
    if entries:
        single = _canon_entry(
            invoke_rest(
                ctx,
                step="CAP-OUT-05:entry",
                method="GET",
                path=f"{base}/{entries[0].id}",
            )
        )
    return CanonReadRecord(series_id=series_id, entries=entries, single=single)


class SeriesCanonReadDriver:
    """CAP-OUT-05 — series-canon read; requires ``targets['series_id']``."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-OUT-05", ctx, _drive_series_canon)


# ---------------------------------------------------------------------------
# CAP-OUT-06 — WikiReadDriver: index + summaries; prose recorded-not-scored
# ---------------------------------------------------------------------------


def _summary_prose(body: object) -> WikiSummaryProse:
    """``WikiSummaryResponse`` (prose carried raw — see the record doc)."""
    return WikiSummaryProse(
        entity_id=as_text(response_field(body, "entity_id")),
        status=as_text(response_field(body, "status")),
        narrative_summary=as_text(response_field(body, "narrative_summary")),
        role_in_story=as_opt_text(response_field(body, "role_in_story")),
    )


def _drive_wiki_read(ctx: CapabilityContext) -> WikiReadRecord:
    base = f"/api/v1/novels/{ctx.novel_id}/wiki"
    index = invoke_rest(ctx, step="CAP-OUT-06:index", method="GET", path=f"{base}/index")
    listed = invoke_rest(ctx, step="CAP-OUT-06:summaries", method="GET", path=f"{base}/summaries")
    summaries = tuple(
        _summary_prose(summary)
        for summary in as_list(response_field(listed, "items"), "summary list")
    )
    single: WikiSummaryProse | None = None
    entity_id = ctx.targets.get("entry_id")
    if entity_id is not None:
        single = _summary_prose(
            invoke_rest(
                ctx,
                step="CAP-OUT-06:summary",
                method="GET",
                path=f"{base}/summaries/{entity_id}",
            )
        )
    chapter_summary: str | None = None
    chapter_summary_status: str | None = None
    chapter_id = next(iter(ctx.chapter_ids.values()), None)
    if chapter_id is not None:
        body = invoke_rest(
            ctx,
            step="CAP-OUT-06:chapter-summary",
            method="GET",
            path=f"{base}/chapters/{chapter_id}/summary",
        )
        chapter_summary = as_text(response_field(body, "narrative_summary"))
        chapter_summary_status = as_text(response_field(body, "status"))
    return WikiReadRecord(
        total_summaries=as_int(response_field(index, "total_summaries")),
        fresh_count=as_int(response_field(index, "fresh_count")),
        stale_count=as_int(response_field(index, "stale_count")),
        pending_count=as_int(response_field(index, "pending_count")),
        summaries=summaries,
        single=single,
        chapter_summary=chapter_summary,
        chapter_summary_status=chapter_summary_status,
    )


class WikiReadDriver:
    """CAP-OUT-06 — wiki overview/summaries; prose recorded-not-scored."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-OUT-06", ctx, _drive_wiki_read)


# ---------------------------------------------------------------------------
# CAP-OUT-07 — TimelineReadDriver: events + first read-back + age report
# ---------------------------------------------------------------------------


def _event_ref(body: object) -> TimelineEventRef:
    """``TimelineEventCRUDResponse`` scoring fields."""
    return TimelineEventRef(
        id=as_text(response_field(body, "id")),
        event_name=as_text(response_field(body, "event_name")),
        event_type=as_text(response_field(body, "event_type")),
        timestamp_raw=as_text(response_field(body, "timestamp_raw")),
        source=as_text(response_field(body, "source")),
        confidence=as_opt_float(response_field(body, "confidence")),
        is_confirmed=as_bool(response_field(body, "is_confirmed")),
        chapter_id=as_opt_text(response_field(body, "chapter_id")),
    )


def _character_age(body: object) -> CharacterAge:
    """``CharacterAgeInfo`` row."""
    return CharacterAge(
        character_name=as_text(response_field(body, "character_name")),
        character_id=as_opt_text(response_field(body, "character_id")),
        birth_date=as_opt_text(response_field(body, "birth_date")),
        birth_date_narrative=as_opt_text(response_field(body, "birth_date_narrative")),
        age_available=as_bool(response_field(body, "age_available")),
    )


def _drive_timeline_read(ctx: CapabilityContext) -> TimelineReadRecord:
    base = f"/api/v1/planning/timeline/{ctx.novel_id}"
    listed = invoke_rest(ctx, step="CAP-OUT-07:events", method="GET", path=f"{base}/events")
    events = tuple(_event_ref(event) for event in as_list(listed, "event list"))
    single: TimelineEventRef | None = None
    if events:
        single = _event_ref(
            invoke_rest(
                ctx,
                step="CAP-OUT-07:event",
                method="GET",
                path=f"{base}/events/{events[0].id}",
            )
        )
    report = invoke_rest(
        ctx, step="CAP-OUT-07:character-ages", method="GET", path=f"{base}/character-ages"
    )
    return TimelineReadRecord(
        events=events,
        single=single,
        ages=tuple(
            _character_age(character)
            for character in as_list(response_field(report, "characters"), "character list")
        ),
        characters_with_age=as_int(response_field(report, "characters_with_age")),
        characters_without_age=as_int(response_field(report, "characters_without_age")),
    )


class TimelineReadDriver:
    """CAP-OUT-07 — timeline read + character-age report (un-paginated list)."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-OUT-07", ctx, _drive_timeline_read)


SURFACES_OUT_DRIVERS: Final[dict[str, type[CapabilityDriver]]] = {
    "CAP-OUT-05": SeriesCanonReadDriver,
    "CAP-OUT-06": WikiReadDriver,
    "CAP-OUT-07": TimelineReadDriver,
}
"""cap_id → driver class for the read-surface half (facade-assembled)."""
