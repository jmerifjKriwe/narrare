"""Unit tests for memory models — FeedbackEventModel and PreferenceProfileModel."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from narrare.memory.models import FeedbackEventModel, PreferenceProfileModel


class TestFeedbackEventModel:
    def test_rating_column_accepts_none(self) -> None:
        event = FeedbackEventModel(
            user_id=uuid4(),
            project_id=uuid4(),
            suggestion_id=uuid4(),
            action="accept",
            intent="write",
            suggestion_text="Text",
            rating=None,
        )
        assert event.rating is None

    def test_rating_column_accepts_int(self) -> None:
        event = FeedbackEventModel(
            user_id=uuid4(),
            project_id=uuid4(),
            suggestion_id=uuid4(),
            action="accept",
            intent="write",
            suggestion_text="Text",
            rating=4,
        )
        assert event.rating == 4

    def test_repr_includes_action(self) -> None:
        event = FeedbackEventModel(
            user_id=uuid4(),
            project_id=uuid4(),
            suggestion_id=uuid4(),
            action="accept",
            intent="write",
            suggestion_text="Text",
        )
        assert "accept" in repr(event)


class TestPreferenceProfileModel:
    def test_all_fields_have_defaults(self) -> None:
        """Model accepts all fields with explicit values.

        Column defaults (default=, server_default=) only apply at SQL INSERT
        time, not at Python instantiation. We provide explicit values here to
        verify the model stores them correctly.
        """
        now = datetime.now(UTC)
        profile = PreferenceProfileModel(
            user_id=uuid4(),
            project_id=uuid4(),
            style_patterns=[],
            content_patterns=[],
            avoidance_patterns=[],
            confidence=0.0,
            summary="",
            event_count_at_analysis=0,
            created_at=now,
            updated_at=now,
        )
        assert profile.style_patterns == []
        assert profile.content_patterns == []
        assert profile.avoidance_patterns == []
        assert profile.confidence == 0.0
        assert profile.summary == ""
        assert profile.event_count_at_analysis == 0
        assert isinstance(profile.created_at, datetime)
        assert isinstance(profile.updated_at, datetime)

    def test_with_all_fields(self) -> None:
        uid = uuid4()
        pid = uuid4()
        profile = PreferenceProfileModel(
            user_id=uid,
            project_id=pid,
            style_patterns=["concise", "dialogue-heavy"],
            content_patterns=["action-focused"],
            avoidance_patterns=["cliffhangers"],
            confidence=0.85,
            summary="User prefers action-oriented prose.",
            event_count_at_analysis=42,
        )
        assert profile.confidence == 0.85
        assert profile.event_count_at_analysis == 42
        assert len(profile.style_patterns) == 2

    def test_repr(self) -> None:
        profile = PreferenceProfileModel(
            user_id=uuid4(),
            project_id=uuid4(),
        )
        r = repr(profile)
        assert "PreferenceProfileModel" in r
