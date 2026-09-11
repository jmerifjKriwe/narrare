"""Unit tests for the ingest raw-event sink (``benchmark.ingest_events``).

Pinned via the driver: one event per HTTP exchange in call order with the
pinned step names, chapter scoping, statuses, and non-negative timing; and
deep-copy sanitization — sensitive keys redacted at any depth by a
recursive rebuild, the backend's source objects untouched, and no secret
value anywhere in the events' ``repr``. Headers are never recorded at all.
"""

from __future__ import annotations

from typing import cast

from benchmark.ingest_events import REDACTED
from benchmark.tests.ingest_helpers import CHAPTERS, ingest_responder, run_ingest


def test_event_sink_records_every_call_in_order_with_timing() -> None:
    api, events, _result = run_ingest("incremental")

    assert len(events) == len(api.calls) == 1 + 4 * len(CHAPTERS)
    steps = [event.step for event in events]
    assert steps == [
        "create_novel",
        "create_chapter",
        "set_content",
        "extract",
        "endorse",
        "create_chapter",
        "set_content",
        "extract",
        "endorse",
    ]
    assert events[0].chapter_stem is None
    assert events[1].chapter_stem == "ch-01"
    assert events[4].chapter_stem == "ch-01"
    assert events[5].chapter_stem == "ch-02"
    for event, call in zip(events, api.calls, strict=True):
        assert event.method == call.method
        assert event.path == call.path
        assert event.elapsed_seconds >= 0.0
    assert [event.status for event in events] == [201, 201, 200, 200, 200, 201, 200, 200, 200]


def test_event_bodies_are_sanitized_deep_copies() -> None:
    leak: dict[str, object] = {
        "api_key": "sk-leak-1",
        "access_token": "tok-leak-2",
        "authorization": "Bearer bearer-leak-3",
        "nested": {"password": "pw-leak-4", "note": "keep-me"},
    }
    _api, events, _result = run_ingest("incremental", ingest_responder(leak=leak))

    extract_event = next(event for event in events if event.step == "extract")
    raw_body = extract_event.response_body
    assert isinstance(raw_body, dict)
    body = cast("dict[str, object]", raw_body)
    assert body["api_key"] == REDACTED
    assert body["access_token"] == REDACTED
    assert body["authorization"] == REDACTED
    raw_nested = body["nested"]
    assert isinstance(raw_nested, dict)
    nested = cast("dict[str, object]", raw_nested)
    assert nested["password"] == REDACTED
    assert nested["note"] == "keep-me"
    # The sink is a deep copy: the source object the backend built is untouched.
    assert leak["api_key"] == "sk-leak-1"
    serialized = "\n".join(repr(event) for event in events)
    assert "sk-leak-1" not in serialized
    assert "tok-leak-2" not in serialized
    assert "bearer-leak-3" not in serialized
    assert "pw-leak-4" not in serialized
