"""Unit tests for the E2E mock catalog (spec §3 + §10).

Every catalog entry must validate against the REAL app pydantic models —
this is the drift-ratchet the spec demands, runnable without a stack.
"""

from __future__ import annotations

import pytest

from tests.e2e.mocks.catalog import (
    CATALOG,
    assert_sse_body_wellformed,
    entries_for,
    validate_catalog,
)


class TestRegistry:
    def test_every_spec_has_body_pattern_and_capability(self) -> None:
        for spec in CATALOG:
            assert spec.body, f"{spec.capability}/{spec.variant}: empty body"
            assert spec.pattern.startswith("**/api/v1/"), spec.pattern
            assert spec.variant in {"happy", "error"}

    def test_entries_for_raises_on_unknown_capability(self) -> None:
        with pytest.raises(ValueError, match="Unknown capability"):
            entries_for("telepathy", "happy")

    def test_entries_for_raises_on_unknown_variant(self) -> None:
        with pytest.raises(ValueError, match="Unknown capability"):
            entries_for("generation_stream", "sad")


class TestSseWellformedness:
    def test_parses_events_and_requires_done_sentinel(self) -> None:
        body = 'data: {"text": "hi"}\n\ndata: [DONE]\n\n'
        events = assert_sse_body_wellformed(body)
        assert events == [{"text": "hi"}]

    def test_rejects_missing_done_sentinel(self) -> None:
        with pytest.raises(ValueError, match="missing terminal"):
            assert_sse_body_wellformed('data: {"text": "hi"}\n\n')

    def test_rejects_malformed_json_payload(self) -> None:
        with pytest.raises(ValueError):
            assert_sse_body_wellformed("data: {not json}\n\ndata: [DONE]\n\n")


class TestWritingEntries:
    def test_generation_stream_has_happy_and_error_variants(self) -> None:
        assert {s.variant for s in entries_for("generation_stream", "happy")} == {"happy"}
        assert {s.variant for s in entries_for("generation_stream", "error")} == {"error"}

    def test_generation_happy_stream_is_final_and_done_terminated(self) -> None:
        spec = entries_for("generation_stream", "happy")[0]
        assert spec.method == "GET"
        assert spec.content_type == "text/event-stream"
        events = assert_sse_body_wellformed(spec.body)
        assert events[0]["type"] == "context_meta"
        assert any(e.get("is_final") is True for e in events)

    def test_scene_fixtures_validate_against_real_models(self) -> None:
        validate_catalog()  # full ratchet; writing part asserted here by absence of raise
        happy = {s.capability: s for s in CATALOG if s.variant == "happy"}
        assert "scene_draft" in happy
        assert "scene_refine" in happy
