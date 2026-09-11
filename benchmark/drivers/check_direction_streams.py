"""CHECK-direction SSE drivers — flavor-B analysis streams (plan Task 10).

The three SSE check drivers on the analysis routes (map §6 flavor B:
type-discriminated ``event`` envelope, terminal ``done``/``error`` +
``[DONE]`` sentinel; ``benchmark.drivers.check_direction`` holds the REST
half plus the direction's registration facade):

- CAP-CHK-05 ``VoiceCheckDriver`` — chapter-scoped per-character voice
  verdicts (``analysis/router_voice_check.py``; the router declares NO
  request body).
- CAP-CHK-06 ``VoiceDriftDriver`` — novel-scoped longitudinal
  per-character drift (``analysis/router_voice_drift.py``).
- CAP-CHK-07 ``AuthorVoiceDriftDriver`` — novel-scoped narrator drift
  (``analysis/router_author_voice_drift.py``).

Stream-event dispatch (router-verified): the voice-drift stream emits
``character_result``/``no_profile`` event types, and the author stream a
``no_profile`` type — beyond the generic flavor-B set. ``benchmark.sse``
decodes only progress/result/done/error specially, so those additional
types arrive as fallback ``SseItem`` events and are dispatched here on
the payload's ``event`` key; any OTHER item event type is protocol drift
(``StreamProtocolError`` → ERROR). The author stream's ``result`` and
``no_profile`` are mutually exclusive on the wire (one narrator per
novel) — the driver enforces that, too.

Terminal handling: ``check_terminal`` fails in-band ``error`` events and
missing terminals; an SSE total-deadline breach raises
``SseDeadlineError`` — ``guarded`` converts both into ERROR results.
CAP-CHK-05 requires the run's first ingested chapter
(``targets['chapter_id']``, same contract as CAP-IN-01); the novel-scoped
06/07 always drive. Failure/typing contract: see
``benchmark.drivers.in_parsing``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.drivers.check_direction_series import (
    author_drift_result,
    drift_verdict,
    jump_point,
    trend_point,
)
from benchmark.drivers.check_records import (
    AuthorVoiceDriftRecord,
    CharacterDriftResult,
    FlaggedLine,
    VoiceCheckFinding,
    VoiceCheckRecord,
    VoiceDriftNoProfileRef,
    VoiceDriftRecord,
)
from benchmark.drivers.in_parsing import (
    StreamProtocolError,
    as_bool,
    as_int,
    as_list,
    as_opt_float,
    as_opt_text,
    as_text,
    check_terminal,
    guarded,
    require_target,
    response_field,
)
from benchmark.drivers.shapes import invoke_sse
from benchmark.sse import SseItem, SseProgress, SseResult

if TYPE_CHECKING:
    from benchmark.drivers.base import CapabilityContext, CapabilityResult

ANALYSIS_BASE: Final[str] = "/api/v1/analysis"
"""Analysis-router mount prefix (``analysis/*`` routers, map §7)."""


# ---------------------------------------------------------------------------
# CAP-CHK-05 — VoiceCheckDriver: per-character verdicts (chapter-scoped)
# ---------------------------------------------------------------------------


def _flagged_line(body: object) -> FlaggedLine:
    return FlaggedLine(
        quote=as_text(response_field(body, "quote")),
        reason=as_text(response_field(body, "reason")),
    )


def _voice_check_finding(body: object) -> VoiceCheckFinding:
    """``VoiceCheckResult`` — complete (analysis/schemas_voice_check)."""
    return VoiceCheckFinding(
        character_name=as_text(response_field(body, "character_name")),
        match_score=as_opt_float(response_field(body, "match_score")),
        band=as_opt_text(response_field(body, "band")),
        match_judgment=as_opt_text(response_field(body, "match_judgment")),
        qualitative_sub_score=as_opt_float(response_field(body, "qualitative_sub_score")),
        metric_delta_subscore=as_opt_float(response_field(body, "metric_delta_subscore")),
        flagged_lines=tuple(
            _flagged_line(line)
            for line in as_list(response_field(body, "flagged_lines"), "flagged-line list")
        ),
        has_profile=as_bool(response_field(body, "has_profile")),
        n_comparable_metrics=as_int(response_field(body, "n_comparable_metrics")),
    )


def _drive_voice_check(ctx: CapabilityContext) -> VoiceCheckRecord:
    chapter_id = require_target(ctx, "chapter_id")
    stream = invoke_sse(
        ctx,
        step="CAP-CHK-05",
        path=f"{ANALYSIS_BASE}/voice-check/{chapter_id}",
    )
    check_terminal(stream.terminal, "CAP-CHK-05")
    return VoiceCheckRecord(
        chapter_id=chapter_id,
        characters=tuple(
            _voice_check_finding(response_field(item.payload, "result"))
            for item in stream.events
            if isinstance(item, SseResult)
        ),
        progress_messages=tuple(
            as_text(response_field(item.payload, "progress"))
            for item in stream.events
            if isinstance(item, SseProgress)
        ),
    )


class VoiceCheckDriver:
    """CAP-CHK-05 — chapter voice check on ``targets['chapter_id']``."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-CHK-05", ctx, _drive_voice_check)


# ---------------------------------------------------------------------------
# CAP-CHK-06 — VoiceDriftDriver: character_result / no_profile dispatch
# ---------------------------------------------------------------------------


def _character_drift(body: object) -> CharacterDriftResult:
    """``VoiceDriftCharacterResult`` — complete (analysis/schemas_voice_drift)."""
    return CharacterDriftResult(
        character_id=as_text(response_field(body, "character_id")),
        character_name=as_text(response_field(body, "character_name")),
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


def _no_profile_ref(body: object) -> VoiceDriftNoProfileRef:
    """``VoiceDriftNoProfile`` — complete graceful-skip detail."""
    return VoiceDriftNoProfileRef(
        character_id=as_text(response_field(body, "character_id")),
        character_name=as_text(response_field(body, "character_name")),
        reason=as_text(response_field(body, "reason")),
    )


def _item_event(item: SseItem) -> object:
    event = item.payload.get("event")
    if not isinstance(event, str):
        raise StreamProtocolError(
            f"fallback stream event without an event discriminator: {item.payload!r}"
        )
    return event


def _drive_voice_drift(ctx: CapabilityContext) -> VoiceDriftRecord:
    stream = invoke_sse(
        ctx,
        step="CAP-CHK-06",
        path=f"{ANALYSIS_BASE}/voice-drift/{ctx.novel_id}",
        json_body={"character_id": None, "chapter_ids": None},
    )
    check_terminal(stream.terminal, "CAP-CHK-06")
    characters: list[CharacterDriftResult] = []
    no_profiles: list[VoiceDriftNoProfileRef] = []
    progress: list[str] = []
    for item in stream.events:
        if isinstance(item, SseProgress):
            progress.append(as_text(response_field(item.payload, "progress")))
        elif isinstance(item, SseResult):
            raise StreamProtocolError(
                "CAP-CHK-06 emits 'character_result' events, not plain 'result'"
            )
        else:  # SseItem — the character_result / no_profile fallback events
            event = _item_event(item)
            if event == "character_result":
                characters.append(_character_drift(response_field(item.payload, "result")))
            elif event == "no_profile":
                no_profiles.append(_no_profile_ref(response_field(item.payload, "no_profile")))
            else:
                raise StreamProtocolError(f"undocumented CAP-CHK-06 stream event {event!r}")
    return VoiceDriftRecord(
        characters=tuple(characters),
        no_profiles=tuple(no_profiles),
        progress_messages=tuple(progress),
    )


class VoiceDriftDriver:
    """CAP-CHK-06 — longitudinal character drift over the run's novel."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-CHK-06", ctx, _drive_voice_drift)


# ---------------------------------------------------------------------------
# CAP-CHK-07 — AuthorVoiceDriftDriver: singular narrator result xor skip
# ---------------------------------------------------------------------------


def _drive_author_voice_drift(ctx: CapabilityContext) -> AuthorVoiceDriftRecord:
    stream = invoke_sse(
        ctx,
        step="CAP-CHK-07",
        path=f"{ANALYSIS_BASE}/author-voice-drift/{ctx.novel_id}",
        json_body={"chapter_ids": None},
    )
    check_terminal(stream.terminal, "CAP-CHK-07")
    result = None
    no_profile_reason: str | None = None
    progress: list[str] = []
    for item in stream.events:
        if isinstance(item, SseProgress):
            progress.append(as_text(response_field(item.payload, "progress")))
        elif isinstance(item, SseResult):
            result = author_drift_result(response_field(item.payload, "result"))
        else:  # SseItem — the no_profile fallback event
            event = _item_event(item)
            if event == "no_profile":
                no_profile_reason = as_text(
                    response_field(response_field(item.payload, "no_profile"), "reason")
                )
            else:
                raise StreamProtocolError(f"undocumented CAP-CHK-07 stream event {event!r}")
    if result is not None and no_profile_reason is not None:
        raise StreamProtocolError(
            "CAP-CHK-07: result and no_profile are mutually exclusive (one narrator)"
        )
    return AuthorVoiceDriftRecord(
        result=result,
        no_profile_reason=no_profile_reason,
        progress_messages=tuple(progress),
    )


class AuthorVoiceDriftDriver:
    """CAP-CHK-07 — narrator drift vs the author-voice profile."""

    def invoke(self, ctx: CapabilityContext) -> CapabilityResult:
        return guarded("CAP-CHK-07", ctx, _drive_author_voice_drift)
