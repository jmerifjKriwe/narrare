"""Unit tests for ``benchmark.sse`` — parser core + stream collector.

Both documented flavors (benchmark/docs/api-surface.md §6) are exercised
against realistic recorded byte fixtures: flavor A (data-only raw item
frames, in-band ``{"error", "code"}`` frames, ``[DONE]`` sentinel) and
flavor B (``CoreferenceStreamEvent`` envelopes with ``is_final``, extra
observability keys). Malformed input, keep-alive comments, multi-line
data, CRLF endings and protocol violations (stream without terminal)
are covered. No network.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from benchmark.sse import (
    DONE_SENTINEL,
    SseDone,
    SseErrorEvent,
    SseItem,
    SseParseError,
    SseProgress,
    SseResult,
    SseSentinel,
    SseStreamResult,
    collect_events,
    decode_frame,
    parse_frames,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

FLAVOR_A_STREAM = (
    b'data: {"id":"ev-1","expression":"Klaus betrat die Bibliothek.",'
    b'"event_name":"Ankunft","chapter_reference":"Kapitel 1",'
    b'"character_names":["Klaus"],"location_name":"Bibliothek",'
    b'"confidence":0.92,"context":"Er suchte das alte Buch."}\n\n'
    b'data: {"id":"ev-2","expression":"Mira versteckte den Brief hinter '
    b'dem Gem\xc3\xa4lde.","event_name":"Verstecken","chapter_reference":'
    b'"Kapitel 1","character_names":["Mira"],"location_name":"Bibliothek",'
    b'"confidence":0.87,"context":"Niemand sah ihr zu."}\n\n'
    b"data: [DONE]\n\n"
)

FLAVOR_A_ERROR_STREAM = (
    b'data: {"error":"Novel 999 not found","code":"NOT_FOUND"}\n\ndata: [DONE]\n\n'
)

FLAVOR_B_STREAM = (
    b'data: {"event":"progress","progress":"Analysiere 3 Kapitel",'
    b'"is_final":false}\n\n'
    b'data: {"event":"result","result":{"character_name":"Klaus",'
    b'"voice_analysis":{"tone":"trocken","pace":"langsam"},'
    b'"distinctiveness_notes":"Ironischer Unterton","kb_entry_id":"kb-77"},'
    b'"is_final":false}\n\n'
    b'data: {"event":"done","is_final":true}\n\n'
    b"data: [DONE]\n\n"
)

FLAVOR_B_ERROR_STREAM = (
    b'data: {"event":"error","error":"Keine Kapitel mit Inhalt","is_final":true}\n\n'
    b"data: [DONE]\n\n"
)

SSE_HEADERS_NOT_NEEDED = None  # fixtures are raw bytes; no transport involved


def lines_of(raw: bytes) -> list[str]:
    return raw.decode(
        "utf-8"
    ).splitlines()  # --- Flavor A: raw item frames + [DONE] sentinel -------------------------


def test_flavor_a_items_collected_until_sentinel() -> None:
    result = collect_events(lines_of(FLAVOR_A_STREAM))

    assert len(result.events) == 2
    first, second = result.events
    assert isinstance(first, SseItem) and isinstance(second, SseItem)
    assert first.payload["id"] == "ev-1"
    assert first.payload["expression"] == "Klaus betrat die Bibliothek."
    assert second.payload["confidence"] == 0.87
    assert isinstance(result.terminal, SseSentinel)


def test_flavor_a_in_band_error_is_terminal_with_code() -> None:
    result = collect_events(lines_of(FLAVOR_A_ERROR_STREAM))

    assert result.events == ()
    assert isinstance(result.terminal, SseErrorEvent)
    assert result.terminal.message == "Novel 999 not found"
    assert result.terminal.code == "NOT_FOUND"


@pytest.mark.parametrize("code", ["NOT_FOUND", "CONFIG_ERROR", "INTERNAL"])
def test_flavor_a_all_documented_error_codes_terminal(code: str) -> None:
    raw = f'data: {{"error":"boom","code":"{code}"}}\n\ndata: [DONE]\n\n'

    result = collect_events(raw.splitlines())

    assert isinstance(result.terminal, SseErrorEvent)
    assert result.terminal.code == code


# --- Flavor B: type-discriminated envelopes ------------------------------


def test_flavor_b_progress_result_done_sequence() -> None:
    result = collect_events(lines_of(FLAVOR_B_STREAM))

    assert len(result.events) == 2
    progress, item_result = result.events
    assert isinstance(progress, SseProgress)
    assert progress.payload["progress"] == "Analysiere 3 Kapitel"
    assert isinstance(item_result, SseResult)
    inner = item_result.payload["result"]
    assert isinstance(inner, dict)
    assert inner["character_name"] == "Klaus"
    assert isinstance(result.terminal, SseDone)
    assert result.terminal.payload["is_final"] is True


def test_flavor_b_error_event_is_terminal_without_code() -> None:
    result = collect_events(lines_of(FLAVOR_B_ERROR_STREAM))

    assert result.events == ()
    assert isinstance(result.terminal, SseErrorEvent)
    assert result.terminal.message == "Keine Kapitel mit Inhalt"
    assert result.terminal.code is None


def test_flavor_b_tolerates_extra_observability_keys() -> None:
    raw = (
        b'data: {"event":"progress","progress":"Schritt 1","is_final":false,'
        b'"x_trace_id":"t-1","x_span_id":"s-2"}\n\n'
        b"data: [DONE]\n\n"
    )

    result = collect_events(lines_of(raw))

    assert len(result.events) == 1
    assert isinstance(result.events[0], SseProgress)
    assert result.events[0].payload["x_trace_id"] == "t-1"


# --- Line-parser core ------------------------------------------------------


def test_multiline_data_lines_join_into_one_event() -> None:
    raw = (
        b'data: {"id":"ml-1",\n'
        b'data:  "expression":"Zwei Zeilen","confidence":0.5}\n\n'
        b"data: [DONE]\n\n"
    )

    frames = list(parse_frames(raw.decode("utf-8").splitlines()))

    assert len(frames) == 2
    assert frames[0].data == '{"id":"ml-1",\n "expression":"Zwei Zeilen","confidence":0.5}'
    decoded = decode_frame(frames[0])
    assert isinstance(decoded, SseItem)
    assert decoded.payload["expression"] == "Zwei Zeilen"


def test_keep_alive_comments_are_ignored() -> None:
    raw = (
        b": keep-alive ping\n\n"
        b'data: {"id":"k-1","expression":"x","confidence":1.0}\n\n'
        b": keep-alive\n"
        b"data: [DONE]\n\n"
    )

    result = collect_events(lines_of(raw))

    assert len(result.events) == 1
    assert isinstance(result.events[0], SseItem)
    assert isinstance(result.terminal, SseSentinel)


def test_crlf_line_endings_parse_identically() -> None:
    crlf_raw = FLAVOR_A_STREAM.replace(b"\n", b"\r\n")
    result = collect_events(lines_of(crlf_raw))

    assert len(result.events) == 2
    assert isinstance(result.terminal, SseSentinel)


def test_data_field_without_space_recognized() -> None:
    result = collect_events([f"data:{DONE_SENTINEL}", ""])

    assert isinstance(result.terminal, SseSentinel)


def test_event_field_line_is_tolerated_not_required() -> None:
    raw = (
        b"event: progress\n"
        b'data: {"event":"progress","progress":"via Feld","is_final":false}\n\n'
        b"data: [DONE]\n\n"
    )

    frames = list(parse_frames(raw.decode("utf-8").splitlines()))

    assert frames[0].event_name == "progress"
    decoded = decode_frame(frames[0])
    assert isinstance(decoded, SseProgress)
    assert decoded.payload["progress"] == "via Feld"


def test_final_frame_without_trailing_blank_line_is_flushed() -> None:
    frames = list(parse_frames(["data: [DONE]"]))

    assert len(frames) == 1
    assert frames[0].data == DONE_SENTINEL


def test_stream_without_terminal_reports_protocol_violation() -> None:
    raw = b'data: {"id":"x-1","expression":"x","confidence":0.1}\n\n'

    result = collect_events(lines_of(raw))

    assert len(result.events) == 1
    assert result.terminal is None  # caller must treat as protocol violation


def test_empty_stream_yields_zero_events_and_no_terminal() -> None:
    result = collect_events([])

    assert result == SseStreamResult(events=(), terminal=None)


# --- Malformed input -------------------------------------------------------


@pytest.mark.parametrize("bad", ["{nicht-json}", '"nur ein string"', "42"])
def test_malformed_data_frame_raises_parse_error(bad: str) -> None:
    with pytest.raises(SseParseError) as excinfo:
        collect_events([f"data: {bad}", ""])

    assert excinfo.value.raw_data == bad


def test_bare_error_key_without_code_or_event_is_not_terminal() -> None:
    # Parser contract: in-band errors need {"error": str, "code": str}
    # (flavor A) or event=error (flavor B). Anything else stays an item.
    raw = b'data: {"error":"ambiguous"}\n\ndata: [DONE]\n\n'

    result = collect_events(lines_of(raw))

    assert isinstance(result.events[0], SseItem)
    assert isinstance(result.terminal, SseSentinel)


def test_error_event_with_non_string_error_payload_is_terminal() -> None:
    raw = b'data: {"event":"error","error":{"detail":"verschachtelt"},"is_final":true}\n\n'

    result = collect_events(lines_of(raw))

    assert isinstance(result.terminal, SseErrorEvent)
    assert '"verschachtelt"' in result.terminal.message
    assert result.terminal.code is None


# --- collect_events input tolerance ----------------------------------------


def test_collector_accepts_any_str_iterable() -> None:
    def gen() -> Iterable[str]:
        yield from lines_of(FLAVOR_B_STREAM)

    result = collect_events(gen())

    # First terminal wins: event=done ends the stream, the trailing
    # [DONE] sentinel line is never consumed.
    assert isinstance(result.terminal, SseDone)
    assert len(result.events) == 2
