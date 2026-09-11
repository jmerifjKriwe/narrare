"""Unit tests for the CHECK-direction SSE drivers (plan Task 10).

Covers CAP-CHK-05..07 (flavor-B analysis streams): terminal handling
(``done`` success, in-band ``error`` events, total-deadline conversion),
flavor-B payload parsing (per-character verdicts incl. ``flagged_lines``,
``character_result``/``no_profile`` fallback-event dispatch, the singular
author-drift result xor ``no_profile``), and the chapter/series structural
skip contracts. Schema sources are cited per record in
``benchmark.drivers.check_records``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import httpx

from benchmark.drivers.base import CapabilityStatus
from benchmark.drivers.check_direction_streams import (
    AuthorVoiceDriftDriver,
    VoiceCheckDriver,
    VoiceDriftDriver,
)
from benchmark.drivers.check_records import (
    AuthorVoiceDriftRecord,
    VoiceCheckRecord,
    VoiceDriftRecord,
)
from benchmark.tests.check_direction_helpers import (
    AUTHOR_DRIFT,
    AUTHOR_DRIFT_CONFLICTING_SSE,
    AUTHOR_DRIFT_ERROR_SSE,
    AUTHOR_DRIFT_NO_PROFILE_SSE,
    AUTHOR_DRIFT_SSE,
    CHAPTER_ID,
    VOICE_CHECK,
    VOICE_CHECK_ERROR_SSE,
    VOICE_CHECK_SSE,
    VOICE_DRIFT,
    VOICE_DRIFT_ERROR_SSE,
    VOICE_DRIFT_SSE,
    VOICE_DRIFT_UNKNOWN_SSE,
    context,
    invoke,
)
from benchmark.tests.check_direction_helpers import (
    CHAPTER_ID as CHAPTER_TARGET,
)
from benchmark.tests.client_helpers import SSE_RESPONSE_HEADERS, ScriptedApi, make_client

if TYPE_CHECKING:
    from collections.abc import Iterator


def infinite_stream_responder(_index: int, _call: object) -> httpx.Response:
    """Never-terminating keep-alive stream (total-deadline evidence, T3)."""

    def lines() -> Iterator[bytes]:
        while True:
            yield b": keep-alive\n\n"

    return httpx.Response(200, headers=SSE_RESPONSE_HEADERS, content=lines())


# ---------------------------------------------------------------------------
# CAP-CHK-05 — VoiceCheckDriver: chapter-scoped per-character verdicts
# ---------------------------------------------------------------------------


def test_voice_check_driver_streams_results_flagged_lines_and_progress() -> None:
    routes = {f"POST {VOICE_CHECK}": VOICE_CHECK_SSE}

    api, events, parsed = invoke(VoiceCheckDriver, routes, targets={"chapter_id": CHAPTER_TARGET})

    assert api.paths() == [f"POST {VOICE_CHECK}"]
    # The voice-check router declares NO request body (schemas_voice_check).
    assert api.calls[0].body is None
    record = parsed
    assert isinstance(record, VoiceCheckRecord)
    assert record.chapter_id == CHAPTER_ID
    assert record.progress_messages == ("Stimmen werden geprueft",)
    assert [c.character_name for c in record.characters] == ["Anna Meyer", "Ben"]
    profiled = record.characters[0]
    assert profiled.match_score == 42.0
    assert profiled.band == "red"
    assert profiled.match_judgment == "off"
    assert profiled.qualitative_sub_score == 40.0
    assert profiled.metric_delta_subscore == 44.0
    assert profiled.has_profile is True
    assert profiled.n_comparable_metrics == 3
    assert [(line.quote, line.reason) for line in profiled.flagged_lines] == [
        ("Na.", "Zu knapp fuer die gespeicherte Stimme.")
    ]
    unprofiled = record.characters[1]
    assert unprofiled.match_score is None
    assert unprofiled.band is None
    assert unprofiled.has_profile is False
    assert unprofiled.flagged_lines == ()
    assert events[0].step == "CAP-CHK-05"


def test_voice_check_driver_in_band_error_is_error_result() -> None:
    api = ScriptedApi()
    api.respond_with(
        lambda _i, _c: httpx.Response(
            200, headers=SSE_RESPONSE_HEADERS, content=VOICE_CHECK_ERROR_SSE
        )
    )

    result = VoiceCheckDriver().invoke(
        context(make_client(api), targets={"chapter_id": CHAPTER_TARGET})
    )

    assert result.cap_id == "CAP-CHK-05"
    assert result.status is CapabilityStatus.ERROR
    assert result.reason is not None and "Voice-check analysis failed." in result.reason
    assert result.parsed is None


def test_voice_check_driver_without_chapter_target_is_skipped_structural() -> None:
    api = ScriptedApi()

    result = VoiceCheckDriver().invoke(context(make_client(api)))

    assert result.status is CapabilityStatus.SKIPPED
    assert result.reason is not None and "chapter_id" in result.reason
    assert api.calls == []


def test_voice_check_driver_deadline_breach_is_error_result() -> None:
    api = ScriptedApi()
    api.respond_with(infinite_stream_responder)

    ctx = context(
        make_client(api),
        targets={"chapter_id": CHAPTER_TARGET},
    )
    # Shrink the total deadline so this test stays fast.
    ctx = replace(ctx, config=replace(ctx.config, sse_deadline_seconds=0.05))
    result = VoiceCheckDriver().invoke(ctx)

    assert result.cap_id == "CAP-CHK-05"
    assert result.status is CapabilityStatus.ERROR
    assert result.reason is not None and "deadline" in result.reason


# ---------------------------------------------------------------------------
# CAP-CHK-06 — VoiceDriftDriver: character_result / no_profile dispatch
# ---------------------------------------------------------------------------


def test_voice_drift_driver_dispatches_character_results_and_no_profiles() -> None:
    routes = {f"POST {VOICE_DRIFT}": VOICE_DRIFT_SSE}

    api, events, parsed = invoke(VoiceDriftDriver, routes)

    assert api.paths() == [f"POST {VOICE_DRIFT}"]
    assert api.calls[0].body == {"character_id": None, "chapter_ids": None}
    assert isinstance(parsed, VoiceDriftRecord)
    assert parsed.progress_messages == ("2 Charaktere",)
    assert [c.character_name for c in parsed.characters] == ["Anna Meyer"]
    character = parsed.characters[0]
    assert character.character_id == "entry-9"
    assert [(t.chapter_id, t.match_subscore, t.band) for t in character.trend] == [
        ("chapter-1", 88.0, "stable"),
        ("chapter-2", 61.0, "moderate"),
    ]
    assert character.jumps[0].jumped_metrics == ("avg_sentence_length",)
    assert character.overall_match_score == 74.5
    assert character.overall_band == "minor"
    assert character.drift.drift_type == "inconsistency"
    assert character.drift.suggested_attention == ("chapter-2",)
    assert [(np.character_name, np.reason) for np in parsed.no_profiles] == [
        ("Ben", "no_stored_profile")
    ]
    assert parsed.no_profiles[0].character_id == ""
    assert events[0].step == "CAP-CHK-06"


def test_voice_drift_driver_in_band_error_is_error_result() -> None:
    api = ScriptedApi()
    api.respond_with(
        lambda _i, _c: httpx.Response(
            200, headers=SSE_RESPONSE_HEADERS, content=VOICE_DRIFT_ERROR_SSE
        )
    )

    result = VoiceDriftDriver().invoke(context(make_client(api)))

    assert result.cap_id == "CAP-CHK-06"
    assert result.status is CapabilityStatus.ERROR
    assert result.reason is not None and "Voice-drift analysis failed." in result.reason


def test_voice_drift_driver_undocumented_item_event_is_protocol_drift() -> None:
    api = ScriptedApi()
    api.respond_with(
        lambda _i, _c: httpx.Response(
            200, headers=SSE_RESPONSE_HEADERS, content=VOICE_DRIFT_UNKNOWN_SSE
        )
    )

    result = VoiceDriftDriver().invoke(context(make_client(api)))

    assert result.status is CapabilityStatus.ERROR
    assert result.reason is not None and "mystery" in result.reason


# ---------------------------------------------------------------------------
# CAP-CHK-07 — AuthorVoiceDriftDriver: singular narrator result xor skip
# ---------------------------------------------------------------------------


def test_author_voice_drift_driver_parses_the_single_narrator_result() -> None:
    routes = {f"POST {AUTHOR_DRIFT}": AUTHOR_DRIFT_SSE}

    api, events, parsed = invoke(AuthorVoiceDriftDriver, routes)

    assert api.paths() == [f"POST {AUTHOR_DRIFT}"]
    assert api.calls[0].body == {"chapter_ids": None}
    assert isinstance(parsed, AuthorVoiceDriftRecord)
    assert parsed.no_profile_reason is None
    assert parsed.progress_messages == ("2 Kapitel",)
    result = parsed.result
    assert result is not None
    assert result.novel_id == "novel-1"
    assert [(t.chapter_id, t.match_subscore, t.band) for t in result.trend] == [
        ("chapter-1", 90.0, "stable")
    ]
    assert result.jumps == ()
    assert result.overall_match_score == 90.0
    assert result.overall_band == "stable"
    assert result.drift.drift_type == "evolution"
    assert result.drift.confidence == 0.6
    assert events[0].step == "CAP-CHK-07"


def test_author_voice_drift_driver_graceful_no_profile_stream() -> None:
    routes = {f"POST {AUTHOR_DRIFT}": AUTHOR_DRIFT_NO_PROFILE_SSE}

    api, _events, parsed = invoke(AuthorVoiceDriftDriver, routes)

    assert api.paths() == [f"POST {AUTHOR_DRIFT}"]
    assert isinstance(parsed, AuthorVoiceDriftRecord)
    assert parsed.result is None
    assert parsed.no_profile_reason == "no_stored_profile"


def test_author_voice_drift_driver_result_and_no_profile_is_protocol_drift() -> None:
    """The wire schema is singular: result XOR no_profile, never both."""
    api = ScriptedApi()
    api.respond_with(
        lambda _i, _c: httpx.Response(
            200, headers=SSE_RESPONSE_HEADERS, content=AUTHOR_DRIFT_CONFLICTING_SSE
        )
    )

    result = AuthorVoiceDriftDriver().invoke(context(make_client(api)))

    assert result.status is CapabilityStatus.ERROR
    assert result.reason is not None and "mutually exclusive" in result.reason


def test_author_voice_drift_driver_in_band_error_is_error_result() -> None:
    api = ScriptedApi()
    api.respond_with(
        lambda _i, _c: httpx.Response(
            200, headers=SSE_RESPONSE_HEADERS, content=AUTHOR_DRIFT_ERROR_SSE
        )
    )

    result = AuthorVoiceDriftDriver().invoke(context(make_client(api)))

    assert result.cap_id == "CAP-CHK-07"
    assert result.status is CapabilityStatus.ERROR
    assert result.reason is not None and "Author-voice-drift analysis failed." in result.reason
