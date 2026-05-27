"""Contract test: Memory Pydantic schemas match frontend expectations.

The frontend consumes FeedbackResponse, PreferenceResponse,
AnalyzeResponse, etc. Field name and type mismatches cause runtime crashes.
"""

from __future__ import annotations

import uuid


class TestFeedbackRequestContract:
    """FeedbackRequest — request body for recording user feedback."""

    def test_feedback_request_has_required_fields(self) -> None:
        from narrare.memory.schemas import FeedbackRequest

        field_names = set(FeedbackRequest.model_fields.keys())
        for f in ("action", "suggestion_id", "intent", "suggestion_text", "project_id"):
            assert f in field_names, f"FeedbackRequest missing field '{f}'"

    def test_feedback_request_action_has_pattern(self) -> None:
        from narrare.memory.schemas import FeedbackRequest

        field = FeedbackRequest.model_fields["action"]
        # Pydantic stores pattern constraint
        assert hasattr(field, "pattern") or any(
            getattr(m, "pattern", None) is not None for m in getattr(field, "metadata", [])
        ), "FeedbackRequest.action should have a pattern constraint"

    def test_feedback_request_rating_is_optional(self) -> None:
        from narrare.memory.schemas import FeedbackRequest

        field = FeedbackRequest.model_fields["rating"]
        assert field.default is None, "rating should default to None"


class TestFeedbackResponseContract:
    """FeedbackResponse — response after recording feedback."""

    def test_feedback_response_has_required_fields(self) -> None:
        from narrare.memory.schemas import FeedbackResponse

        field_names = set(FeedbackResponse.model_fields.keys())
        for f in ("id", "action", "created_at"):
            assert f in field_names, f"FeedbackResponse missing field '{f}'"

    def test_feedback_response_id_is_uuid(self) -> None:
        from narrare.memory.schemas import FeedbackResponse

        ann = FeedbackResponse.model_fields["id"].annotation
        assert ann is uuid.UUID, f"Expected id to be UUID, got {ann}"


class TestPreferenceResponseContract:
    """PreferenceResponse — aggregated user preferences."""

    def test_preference_response_has_required_fields(self) -> None:
        from narrare.memory.schemas import PreferenceResponse

        field_names = set(PreferenceResponse.model_fields.keys())
        expected = {
            "user_id",
            "project_id",
            "event_count",
            "confidence",
            "style",
            "content",
            "constraints",
            "last_updated",
        }
        missing = expected - field_names
        assert not missing, f"PreferenceResponse is missing fields: {missing}"

    def test_preference_response_style_is_dict(self) -> None:
        from narrare.memory.schemas import PreferenceResponse

        ann = PreferenceResponse.model_fields["style"].annotation
        assert "dict" in str(ann).lower(), f"Expected style to be dict, got {ann}"

    def test_preference_response_constraints_is_list(self) -> None:
        from narrare.memory.schemas import PreferenceResponse

        ann = PreferenceResponse.model_fields["constraints"].annotation
        assert "list" in str(ann).lower(), f"Expected constraints to be list, got {ann}"


class TestResetResponseContract:
    """ResetResponse — response after resetting preferences."""

    def test_reset_response_has_required_fields(self) -> None:
        from narrare.memory.schemas import ResetResponse

        field_names = set(ResetResponse.model_fields.keys())
        for f in ("message", "deleted_count"):
            assert f in field_names, f"ResetResponse missing field '{f}'"

    def test_reset_response_message_is_str(self) -> None:
        from narrare.memory.schemas import ResetResponse

        ann = ResetResponse.model_fields["message"].annotation
        assert ann is str, f"Expected message to be str, got {ann}"


class TestAnalyzeResponseContract:
    """AnalyzeResponse — response after preference analysis."""

    def test_analyze_response_has_required_fields(self) -> None:
        from narrare.memory.schemas import AnalyzeResponse

        field_names = set(AnalyzeResponse.model_fields.keys())
        expected = {
            "id",
            "user_id",
            "project_id",
            "confidence",
            "summary",
            "style_patterns",
            "content_patterns",
            "avoidance_patterns",
            "event_count_at_analysis",
            "created_at",
            "updated_at",
        }
        missing = expected - field_names
        assert not missing, f"AnalyzeResponse is missing fields: {missing}"

    def test_analyze_response_summary_is_str(self) -> None:
        from narrare.memory.schemas import AnalyzeResponse

        ann = AnalyzeResponse.model_fields["summary"].annotation
        assert ann is str, f"Expected summary to be str, got {ann}"

    def test_analyze_response_style_patterns_is_list_of_str(self) -> None:
        from narrare.memory.schemas import AnalyzeResponse

        ann = AnalyzeResponse.model_fields["style_patterns"].annotation
        assert "list" in str(ann).lower(), f"Expected style_patterns to be list, got {ann}"
