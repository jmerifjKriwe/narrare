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
            if spec.capability == "generation_stream":
                # "truncated" models the audit-M06 silent stream death (no
                # is_final, no error) — a deliberate third generation variant.
                assert spec.variant in {"happy", "error", "truncated"}, spec.variant
            else:
                assert spec.variant in {"happy", "error"}, spec.variant

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


class TestAnalysisEntries:
    def test_coreference_happy_envelope_validates_against_real_model(self) -> None:
        from narrare.analysis.schemas_coreference import CoreferenceStreamEvent

        spec = entries_for("coreference_stream", "happy")[0]
        events = assert_sse_body_wellformed(spec.body)
        for event in events:
            CoreferenceStreamEvent.model_validate(event)
        assert events[-1]["event"] == "done"

    def test_character_voice_happy_has_progress_result_done(self) -> None:
        from narrare.analysis.schemas_character_voice import CharacterVoiceStreamEvent

        spec = entries_for("character_voice_stream", "happy")[0]
        events = assert_sse_body_wellformed(spec.body)
        for event in events:
            CharacterVoiceStreamEvent.model_validate(event)
        kinds = [e["event"] for e in events]
        assert kinds[0] == "progress"
        assert kinds.count("result") >= 1
        assert kinds[-1] == "done"

    def test_beta_reader_fixture_validates_and_excludes_deep_dive(self) -> None:
        spec = entries_for("beta_reader", "happy")[0]
        assert spec.url_exclude == "/deep-dive"
        from narrare.analysis.schemas import BetaReaderResponse

        BetaReaderResponse.model_validate_json(spec.body)

    def test_consistency_result_validates_and_stream_excluded_from_check(self) -> None:
        json_spec = entries_for("consistency_check", "happy")[0]
        assert json_spec.url_exclude == "/stream"
        from narrare.consistency.schemas import ConsistencyResponse

        ConsistencyResponse.model_validate_json(json_spec.body)

        sse_spec = entries_for("consistency_stream", "happy")[0]
        events = assert_sse_body_wellformed(sse_spec.body)
        assert events[0]["type"] == "stage"
        assert events[-1]["type"] == "result"


class TestKbWikiEntries:
    def test_extraction_and_improve_exclude_sibling_routes(self) -> None:
        # kb_extraction's pattern also matches POST /kb/extract/apply — it must be
        # excluded alongside /extract/bulk or apply calls get extraction JSON.
        extraction_spec = entries_for("kb_extraction", "happy")[0]
        assert extraction_spec.url_exclude == ("/extract/bulk", "/extract/apply")
        assert entries_for("kb_improve", "happy")[0].url_exclude == "/improve/apply"

    def test_full_catalog_validates(self) -> None:
        validate_catalog()


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


class TestWritingCatalogGrowth:
    def test_generation_stream_truncated_has_no_final_chunk(self) -> None:
        spec = entries_for("generation_stream", "truncated")[0]
        events = assert_sse_body_wellformed(spec.body)
        assert events and events[0]["type"] == "context_meta"
        assert not any(e.get("is_final") for e in events), "truncated = silent death: no is_final"
        assert not any("text" in e for e in events), "truncated emits no draft text"

    def test_rewrite_stream_happy_carries_two_complete_alternatives(self) -> None:
        spec = entries_for("rewrite_stream", "happy")[0]
        assert spec.method == "POST"
        events = assert_sse_body_wellformed(spec.body)
        assert events[0]["type"] == "request_info"
        texts = "".join(str(e.get("text") or "") for e in events)
        assert texts.count('<alternative label="') == texts.count("</alternative>") == 2
        assert any(e.get("is_final") for e in events)

    def test_rewrite_stream_has_error_variant(self) -> None:
        assert entries_for("rewrite_stream", "error")[0].status == 500

    def test_story_suggest_suggestions_validate_against_real_model(self) -> None:
        from narrare_core.agents.story_suggest_types import StorySuggestOutput

        spec = entries_for("story_suggest", "happy")[0]
        events = assert_sse_body_wellformed(spec.body)
        suggestions_event = next(e for e in events if e.get("event") == "suggestions")
        StorySuggestOutput.model_validate({"suggestions": suggestions_event["suggestions"]})
        done = events[-1]
        assert done.get("event") == "done" and done.get("is_final") is True

    def test_story_suggest_has_error_variant(self) -> None:
        assert entries_for("story_suggest", "error")[0].status == 500

    def test_coauthor_stream_final_event_carries_valid_changes(self) -> None:
        from narrare.writing.schemas_coauthor import ChangeDetail

        spec = entries_for("coauthor_stream", "happy")[0]
        assert spec.method == "POST"
        events = assert_sse_body_wellformed(spec.body)
        assert events[0]["type"] == "context_meta"
        final = events[-1]
        assert final.get("is_final") is True
        assert final.get("has_changes") is True
        assert final.get("total_changes") == len(final["changes"])
        for change in final["changes"]:
            ChangeDetail.model_validate(change)  # ChangeDetail.id is a UUID — fixture must use one

    def test_coauthor_stream_has_error_variant(self) -> None:
        assert entries_for("coauthor_stream", "error")[0].status == 500
