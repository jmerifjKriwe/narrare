"""Unit tests for the capability driver framework shapes.

Framework smoke tests (plan Task 7): ``CapabilityResult`` shape rules
(SKIPPED/ERROR carry a reason, OK must not), ``CapabilityTimings``
positivity, frozen ``CapabilityContext``, the event-cursor slicing of
one invocation's raw-event refs, the SSE total-deadline guard against a
keep-alive-forever stream (T3 rider: never hang the runner) plus the
well-formed happy path, REST event recording into the sanitized
ingest-event sink, poll pacing/timeout via an injected sleeper, and the
``PlaceholderDriver`` loud-failure contract (Tasks 8-10 replace entries).
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, cast

import httpx
import pytest

from benchmark.capabilities import CAPABILITIES
from benchmark.corpus_loader import Corpus, Reference
from benchmark.drivers import PlaceholderDriver
from benchmark.drivers.base import (
    CapabilityContext,
    CapabilityResult,
    CapabilityStatus,
    CapabilityTimings,
    mark_events,
    take_events,
)
from benchmark.drivers.shapes import (
    PollTimeoutError,
    SseDeadlineError,
    collect_sse_within_deadline,
    invoke_rest,
    invoke_sse,
    poll_until_done,
)
from benchmark.ingest_events import REDACTED, IngestEvent
from benchmark.tests.client_helpers import (
    SSE_RESPONSE_HEADERS,
    RecordedCall,
    Responder,
    ScriptedApi,
    make_client,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from benchmark.client import BenchmarkClient


def _timings(**overrides: float) -> CapabilityTimings:
    values: dict[str, float] = {
        "sse_deadline_seconds": 5.0,
        "poll_timeout_seconds": 5.0,
        "poll_interval_seconds": 0.01,
    }
    values.update(overrides)
    return CapabilityTimings(**values)


def _empty_corpus() -> Corpus:
    return Corpus(
        stems=(),
        clean=(),
        variants=(),
        reference=Reference(persons=(), places=(), objects=(), relations=(), events=()),
        warnings=(),
    )


def _context(
    client: BenchmarkClient,
    *,
    timings: CapabilityTimings | None = None,
    events: list[IngestEvent] | None = None,
) -> CapabilityContext:
    return CapabilityContext(
        client=client,
        corpus=_empty_corpus(),
        novel_id="novel-1",
        chapter_ids={},
        config=timings if timings is not None else _timings(),
        events=events if events is not None else [],
    )


def _static_json(payload: dict[object, object]) -> Responder:
    def respond(_index: int, _call: RecordedCall) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return respond


def _keep_alive_lines() -> Iterator[str]:
    """Never-terminating SSE line source: keep-alive comments forever (T3)."""
    while True:
        yield ": keep-alive"


def _keep_alive_bytes() -> Iterator[bytes]:
    while True:
        yield b": keep-alive\n\n"


# ---------------------------------------------------------------------------
# CapabilityResult / CapabilityContext / CapabilityTimings shapes
# ---------------------------------------------------------------------------


def test_skipped_result_requires_a_reason() -> None:
    result = CapabilityResult.skipped("CAP-CHK-01", reason="router unmounted (404)")

    assert result.status is CapabilityStatus.SKIPPED
    assert result.reason == "router unmounted (404)"
    assert result.parsed is None
    assert result.raw_events == ()
    with pytest.raises(ValueError, match="SKIPPED"):
        CapabilityResult(cap_id="CAP-CHK-01", status=CapabilityStatus.SKIPPED)


def test_error_result_requires_a_reason_and_ok_forbids_one() -> None:
    ok = CapabilityResult.ok("CAP-OUT-02", parsed={"entries": []}, elapsed_seconds=0.25)
    error = CapabilityResult.error("CAP-OUT-02", reason="HTTP 500: Internal server error")

    assert ok.status is CapabilityStatus.OK and ok.reason is None
    assert error.status is CapabilityStatus.ERROR and error.reason is not None
    with pytest.raises(ValueError, match="OK"):
        CapabilityResult(cap_id="CAP-OUT-02", status=CapabilityStatus.OK, reason="contradiction")
    with pytest.raises(ValueError, match="ERROR"):
        CapabilityResult(cap_id="CAP-OUT-02", status=CapabilityStatus.ERROR)


def test_capability_context_is_frozen() -> None:
    ctx = _context(make_client(ScriptedApi()))
    field = "novel_id"

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(ctx, field, "other-novel")


def test_capability_timings_reject_non_positive_values() -> None:
    with pytest.raises(ValueError, match="sse_deadline_seconds"):
        _timings(sse_deadline_seconds=0.0)
    with pytest.raises(ValueError, match="poll_interval_seconds"):
        _timings(poll_interval_seconds=-1.0)


def test_every_registry_id_is_covered_by_the_placeholder_contract() -> None:
    ctx = _context(make_client(ScriptedApi()))

    for _spec in CAPABILITIES:
        with pytest.raises(NotImplementedError, match="Tasks 8-10"):
            PlaceholderDriver().invoke(ctx)


def test_event_cursor_slices_only_the_events_of_one_invocation() -> None:
    ctx = _context(make_client(ScriptedApi()))
    ctx.events.append(
        IngestEvent(
            step="prior",
            chapter_stem=None,
            method="GET",
            path="/prior",
            status=200,
            elapsed_seconds=0.0,
            request_body=None,
            response_body={},
        )
    )

    cursor = mark_events(ctx)
    ctx.events.append(
        IngestEvent(
            step="mine",
            chapter_stem=None,
            method="GET",
            path="/mine",
            status=200,
            elapsed_seconds=0.0,
            request_body=None,
            response_body={},
        )
    )

    assert [event.step for event in take_events(ctx, cursor)] == ["mine"]


# ---------------------------------------------------------------------------
# SSE shape helper — total deadline (T3 rider) + well-formed streams
# ---------------------------------------------------------------------------


def test_sse_collection_enforces_total_deadline_on_keep_alive_forever_stream() -> None:
    with pytest.raises(SseDeadlineError) as excinfo:
        collect_sse_within_deadline(_keep_alive_lines(), deadline_seconds=0.05)

    assert excinfo.value.deadline_seconds == 0.05
    assert excinfo.value.elapsed_seconds >= 0.05


def test_sse_collection_still_returns_terminal_for_well_formed_stream() -> None:
    lines: Iterator[str] = iter(['data: {"event":"done","is_final":true}', "", "data: [DONE]"])

    result = collect_sse_within_deadline(lines, deadline_seconds=5.0)

    assert result.terminal is not None


def test_invoke_sse_records_deadline_evidence_into_the_sink() -> None:
    def infinite_stream(_index: int, _call: RecordedCall) -> httpx.Response:
        return httpx.Response(200, headers=SSE_RESPONSE_HEADERS, content=_keep_alive_bytes())

    api = ScriptedApi()
    api.respond_with(infinite_stream)
    events: list[IngestEvent] = []
    ctx = _context(
        make_client(api),
        timings=_timings(sse_deadline_seconds=0.05),
        events=events,
    )

    with pytest.raises(SseDeadlineError):
        invoke_sse(ctx, step="CAP-IN-09", path="/api/v1/analysis/character-voice/novel-1")

    assert len(events) == 1
    record = events[0]
    assert record.step == "CAP-IN-09"
    assert record.method == "POST"
    assert record.status == 200
    assert record.response_body == {"event_count": None, "terminal": "deadline-exceeded"}


# ---------------------------------------------------------------------------
# REST + poll shape helpers — event recording, pacing, timeout
# ---------------------------------------------------------------------------


def test_invoke_rest_returns_parsed_body_and_records_sanitized_event() -> None:
    api = ScriptedApi()
    api.respond_with(_static_json({"entries": [], "api_key": "sk-secret"}))
    events: list[IngestEvent] = []
    ctx = _context(make_client(api, access_token="acc-1"), events=events)

    body = invoke_rest(ctx, step="CAP-OUT-01", method="GET", path="/api/v1/novels/n-1/kb/entries")

    assert body == {"entries": [], "api_key": "sk-secret"}
    assert api.paths() == ["GET /api/v1/novels/n-1/kb/entries"]
    assert api.calls[0].authorization == "Bearer acc-1"
    assert len(events) == 1
    record = events[0]
    assert record.step == "CAP-OUT-01"
    assert record.status == 200
    assert record.elapsed_seconds >= 0.0
    assert record.response_body == {"entries": [], "api_key": REDACTED}


def test_poll_until_done_returns_done_body_with_recorded_pacing() -> None:
    payloads: list[dict[object, object]] = [
        {"state": "running"},
        {"state": "running"},
        {"state": "done", "value": 7},
    ]
    api = ScriptedApi()
    api.respond_with(lambda index, _call: httpx.Response(200, json=payloads[index]))
    path = "/api/v1/novels/n-1/wiki/summaries/e-1"
    events: list[IngestEvent] = []
    ctx = _context(make_client(api), events=events)
    sleeps: list[float] = []

    def done(body: object) -> bool:
        return cast("dict[object, object]", body).get("state") == "done"

    body = poll_until_done(
        ctx,
        step="CAP-IN-08",
        method="GET",
        path=path,
        is_done=done,
        sleeper=sleeps.append,
    )

    assert body == {"state": "done", "value": 7}
    assert api.paths() == [f"GET {path}"] * 3
    assert sleeps == [0.01, 0.01]
    assert [record.response_body for record in events] == payloads


def test_poll_until_done_times_out_with_attempt_evidence() -> None:
    api = ScriptedApi()
    api.respond_with(_static_json({"state": "running"}))
    ctx = _context(
        make_client(api),
        timings=_timings(poll_timeout_seconds=0.05, poll_interval_seconds=0.01),
    )

    with pytest.raises(PollTimeoutError) as excinfo:
        poll_until_done(
            ctx,
            step="CAP-IN-08",
            method="GET",
            path="/api/v1/novels/n-1/wiki/summaries/e-1",
            is_done=lambda _body: False,
            sleeper=lambda _seconds: None,
        )

    assert excinfo.value.attempts >= 2
    assert excinfo.value.timeout_seconds == 0.05
