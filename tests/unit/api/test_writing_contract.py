"""Contract test: Writing Pydantic schemas match frontend expectations.

The frontend consumes GenerateRequest/Response, GenerationStatusResponse,
StreamChunk, InlineSuggestRequest/Response, etc. Field name and type
mismatches cause runtime crashes.
"""

from __future__ import annotations

import uuid


class TestGenerateRequestContract:
    """GenerateRequest — request body for starting chapter generation."""

    def test_generate_request_has_required_fields(self) -> None:
        from narrare.writing.schemas import GenerateRequest

        field_names = set(GenerateRequest.model_fields.keys())
        for f in ("mode", "tone", "language"):
            assert f in field_names, f"GenerateRequest missing field '{f}'"

    def test_generate_request_has_mode_enum(self) -> None:
        from narrare.writing.schemas import GenerateRequest, GenerationModeEnum

        ann = GenerateRequest.model_fields["mode"].annotation
        assert ann is GenerationModeEnum, f"Expected mode to be GenerationModeEnum, got {ann}"

    def test_generate_request_has_auto_continue_defaults_false(self) -> None:
        from narrare.writing.schemas import GenerateRequest

        field = GenerateRequest.model_fields["auto_continue"]
        assert field.default is False, f"Expected auto_continue default False, got {field.default}"


class TestGenerateResponseContract:
    """GenerateResponse — response after starting generation."""

    def test_generate_response_has_required_fields(self) -> None:
        from narrare.writing.schemas import GenerateResponse

        field_names = set(GenerateResponse.model_fields.keys())
        for f in ("request_id", "status", "mode"):
            assert f in field_names, f"GenerateResponse missing field '{f}'"

    def test_generate_response_request_id_is_uuid(self) -> None:
        from narrare.writing.schemas import GenerateResponse

        ann = GenerateResponse.model_fields["request_id"].annotation
        assert ann is uuid.UUID, f"Expected request_id to be UUID, got {ann}"


class TestGenerationStatusResponseContract:
    """GenerationStatusResponse — full generation request status."""

    def test_status_response_has_required_fields(self) -> None:
        from narrare.writing.schemas import GenerationStatusResponse

        field_names = set(GenerationStatusResponse.model_fields.keys())
        expected = {
            "request_id",
            "status",
            "mode",
            "word_count",
            "tokens_used",
            "model_id",
            "provider_name",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
        }
        missing = expected - field_names
        assert not missing, f"GenerationStatusResponse is missing fields: {missing}"


class TestStopResponseContract:
    """StopResponse — response after stopping generation."""

    def test_stop_response_has_required_fields(self) -> None:
        from narrare.writing.schemas import StopResponse

        field_names = set(StopResponse.model_fields.keys())
        for f in ("request_id", "status", "word_count"):
            assert f in field_names, f"StopResponse missing field '{f}'"

    def test_stop_response_status_defaults_to_stopped(self) -> None:
        from narrare.writing.schemas import StopResponse

        field = StopResponse.model_fields["status"]
        assert field.default == "stopped", (
            f"Expected status default 'stopped', got {field.default!r}"
        )


class TestAcceptResponseContract:
    """AcceptResponse — response after accepting a draft."""

    def test_accept_response_has_chapter_id(self) -> None:
        from narrare.writing.schemas import AcceptResponse

        field_names = set(AcceptResponse.model_fields.keys())
        for f in ("request_id", "chapter_id", "word_count"):
            assert f in field_names, f"AcceptResponse missing field '{f}'"


class TestRejectResponseContract:
    """RejectResponse — response after rejecting a draft."""

    def test_reject_response_has_status(self) -> None:
        from narrare.writing.schemas import RejectResponse

        field = RejectResponse.model_fields["status"]
        assert field.default == "rejected", (
            f"Expected status default 'rejected', got {field.default!r}"
        )


class TestInlineSuggestRequestContract:
    """InlineSuggestRequest — request for ghost text completion."""

    def test_inline_suggest_has_text_before(self) -> None:
        from narrare.writing.schemas import InlineSuggestRequest

        field_names = set(InlineSuggestRequest.model_fields.keys())
        assert "text_before" in field_names, "InlineSuggestRequest missing 'text_before'"

    def test_inline_suggest_text_after_is_optional(self) -> None:
        from narrare.writing.schemas import InlineSuggestRequest

        field = InlineSuggestRequest.model_fields["text_after"]
        assert field.default is None, "text_after should be optional"

    def test_inline_suggest_language_defaults_to_en(self) -> None:
        from narrare.writing.schemas import InlineSuggestRequest

        field = InlineSuggestRequest.model_fields["language"]
        assert field.default == "en", f"Expected language default 'en', got {field.default!r}"


class TestInlineSuggestResponseContract:
    """InlineSuggestResponse — one chunk of SSE stream."""

    def test_suggest_response_has_text_and_is_final(self) -> None:
        from narrare.writing.schemas import InlineSuggestResponse

        field_names = set(InlineSuggestResponse.model_fields.keys())
        for f in ("text", "is_final"):
            assert f in field_names, f"InlineSuggestResponse missing field '{f}'"

    def test_suggest_response_is_final_defaults_false(self) -> None:
        from narrare.writing.schemas import InlineSuggestResponse

        field = InlineSuggestResponse.model_fields["is_final"]
        assert field.default is False, f"Expected is_final default False, got {field.default}"


class TestSceneNextResponseContract:
    """SceneNextResponse — next scene in scene-by-scene mode."""

    def test_scene_next_has_required_fields(self) -> None:
        from narrare.writing.schemas import SceneNextResponse

        field_names = set(SceneNextResponse.model_fields.keys())
        for f in ("request_id", "scene_number", "status"):
            assert f in field_names, f"SceneNextResponse missing field '{f}'"


class TestGenerationStatsResponseContract:
    """GenerationStatsResponse — aggregated generation statistics."""

    def test_stats_response_has_required_fields(self) -> None:
        from narrare.writing.schemas import GenerationStatsResponse

        field_names = set(GenerationStatsResponse.model_fields.keys())
        expected = {
            "total_generations",
            "success_rate",
            "avg_tokens",
            "avg_word_count",
            "most_used_model",
        }
        missing = expected - field_names
        assert not missing, f"GenerationStatsResponse is missing fields: {missing}"


class TestGenerationModeEnumContract:
    """GenerationModeEnum values must match frontend expectations."""

    def test_enum_has_expected_values(self) -> None:
        from narrare.writing.schemas import GenerationModeEnum

        values = {e.value for e in GenerationModeEnum}
        expected = {
            "full_draft",
            "extend",
            "rewrite",
            "scene_by_scene",
            "interview_assisted",
            "interactive_session",
        }
        missing = expected - values
        assert not missing, f"GenerationModeEnum missing expected values: {missing}"


class TestExtendLengthEnumContract:
    """ExtendLength enum values."""

    def test_enum_has_expected_values(self) -> None:
        from narrare.writing.schemas import ExtendLength

        values = {e.value for e in ExtendLength}
        for v in ("short", "medium", "long"):
            assert v in values, f"ExtendLength missing value '{v}'"


class TestGenerationStatusEnumContract:
    """GenerationStatusEnum values."""

    def test_enum_has_expected_values(self) -> None:
        from narrare.writing.schemas import GenerationStatusEnum

        values = {e.value for e in GenerationStatusEnum}
        expected = {"pending", "streaming", "completed", "stopped", "failed"}
        missing = expected - values
        assert not missing, f"GenerationStatusEnum missing expected values: {missing}"
