"""Tests for FeedbackService._translate_to_memory_text() — translation logic.

Split from ``test_feedback_service.py`` to respect RULE-04 file-size limits.
These tests cover the privacy-safe translation of feedback events into mem0
memory text, including action types, ratings, and context metadata.

See: ADR-045 Decision 8, CONSTRAINTS.md RULE-08/RULE-22.
"""

from __future__ import annotations

from uuid import uuid4

from narrare_core.memory.feedback_service import FeedbackService
from narrare_core.memory.models import FeedbackAction, FeedbackEvent


def _make_event(
    *,
    action: FeedbackAction = FeedbackAction.ACCEPT,
    intent: str = "suggestion",
    suggestion_text: str = "A dark and stormy night approached.",
    modification: str = "",
    rating: int | None = None,
    context: dict[str, object] | None = None,
) -> FeedbackEvent:
    """Helper to build a FeedbackEvent with sensible defaults."""
    return FeedbackEvent(
        user_id=uuid4(),
        project_id=uuid4(),
        suggestion_id=uuid4(),
        action=action,
        intent=intent,
        suggestion_text=suggestion_text,
        modification=modification,
        rating=rating,
        context=context or {},
    )


class TestFeedbackServiceTranslateToMemoryText:
    """Tests for FeedbackService._translate_to_memory_text()."""

    def test_accept_action(self) -> None:
        event = _make_event(
            action=FeedbackAction.ACCEPT,
            intent="rewrite",
            suggestion_text="The sun set over the hills.",
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "accepted a rewrite suggestion" in text
        assert "The sun set over the hills." not in text

    def test_reject_action_without_modification(self) -> None:
        event = _make_event(
            action=FeedbackAction.REJECT,
            intent="character",
            suggestion_text="He walked away slowly.",
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "rejected a character suggestion" in text
        assert "He walked away slowly." not in text

    def test_reject_action_with_modification_as_reason(self) -> None:
        event = _make_event(
            action=FeedbackAction.REJECT,
            intent="plot",
            suggestion_text="Suddenly a dragon appeared.",
            modification="Too clichéd",
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "rejected a plot suggestion" in text
        assert "reason: Too clichéd" in text

    def test_modify_action(self) -> None:
        event = _make_event(
            action=FeedbackAction.MODIFY,
            intent="dialogue",
            suggestion_text="Hello there.",
            modification="Hey, how are you?",
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "modified a dialogue suggestion" in text
        assert "Original:" not in text
        assert "Their version:" not in text
        assert "Hello there." not in text
        assert "Hey, how are you?" not in text

    def test_long_suggestion_text_is_truncated(self) -> None:
        long_text = "x" * 500
        event = _make_event(
            action=FeedbackAction.ACCEPT,
            suggestion_text=long_text,
        )
        text = FeedbackService._translate_to_memory_text(event)

        # The suggestion text portion should be truncated to 200 chars
        assert len(text) < 500


class TestFeedbackServiceTranslateWithRating:
    """Tests for rating inclusion in _translate_to_memory_text()."""

    def test_accept_with_rating_5(self) -> None:
        event = _make_event(
            action=FeedbackAction.ACCEPT,
            intent="rewrite",
            suggestion_text="The sun set over the hills.",
            rating=5,
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "accepted a rewrite suggestion" in text
        assert "rating: 5/5" in text

    def test_reject_with_rating_2(self) -> None:
        event = _make_event(
            action=FeedbackAction.REJECT,
            intent="plot",
            suggestion_text="Suddenly a dragon appeared.",
            modification="Too clichéd",
            rating=2,
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "rejected a plot suggestion" in text
        assert "reason: Too clichéd" in text
        assert "rating: 2/5" in text

    def test_no_rating_excludes_rating_text(self) -> None:
        event = _make_event(
            action=FeedbackAction.ACCEPT,
            suggestion_text="Simple text.",
            rating=None,
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "rating" not in text


class TestFeedbackServiceTranslateWithContext:
    """Tests for enriched context in _translate_to_memory_text()."""

    def test_reject_with_genre_and_mode(self) -> None:
        event = _make_event(
            action=FeedbackAction.REJECT,
            intent="character",
            suggestion_text="He walked away slowly.",
            modification="Out of character",
            context={"genre": "Sci-Fi", "mode": "dialogue"},
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "rejected a character suggestion" in text
        assert "genre: Sci-Fi" in text
        assert "mode: dialogue" in text

    def test_modify_with_chapter_id(self) -> None:
        event = _make_event(
            action=FeedbackAction.MODIFY,
            intent="dialogue",
            suggestion_text="Hello there.",
            modification="Hey, how are you?",
            context={"chapter_id": "ch-042"},
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "modified a dialogue suggestion" in text
        assert "chapter: ch-042" in text

    def test_accept_with_all_context_fields(self) -> None:
        event = _make_event(
            action=FeedbackAction.ACCEPT,
            intent="rewrite",
            suggestion_text="A brilliant sentence.",
            rating=4,
            context={
                "chapter_id": "ch-007",
                "genre": "Fantasy",
                "mode": "narrative",
            },
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "rating: 4/5" in text
        assert "chapter: ch-007" in text
        assert "genre: Fantasy" in text
        assert "mode: narrative" in text

    def test_empty_context_excludes_brackets(self) -> None:
        event = _make_event(
            action=FeedbackAction.ACCEPT,
            suggestion_text="Simple text.",
            context={},
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "[" not in text

    def test_context_with_unrelated_keys_excludes_them(self) -> None:
        event = _make_event(
            action=FeedbackAction.ACCEPT,
            suggestion_text="Text.",
            context={"random_key": "value"},
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "[" not in text
