"""Tests for memory/feedback_service.py — FeedbackService."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

from narrare_core.memory._null_client import NullMemoryClient
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


class TestFeedbackServiceRecord:
    """Tests for FeedbackService.record()."""

    async def test_record_calls_persist_fn_with_event(self) -> None:
        """record() must call the injected persist_fn with the event."""
        persist_fn = AsyncMock()
        mem0 = AsyncMock()
        service = FeedbackService(mem0_client=mem0, persist_fn=persist_fn)

        event = _make_event()
        await service.record(event)

        persist_fn.assert_awaited_once_with(event)

    async def test_record_calls_mem0_add_with_translated_text(self) -> None:
        """record() must forward translated text to mem0.add()."""
        persist_fn = AsyncMock()
        mem0 = AsyncMock()
        service = FeedbackService(mem0_client=mem0, persist_fn=persist_fn)

        event = _make_event()
        await service.record(event)

        mem0.add.assert_awaited_once()
        call_kwargs = mem0.add.call_args[1]
        assert "accepted a suggestion" in call_kwargs["messages"]
        assert call_kwargs["user_id"] == str(event.user_id)
        assert call_kwargs["agent_id"] == str(event.project_id)
        assert call_kwargs["metadata"]["action"] == "accept"
        assert call_kwargs["metadata"]["intent"] == "suggestion"
        assert call_kwargs["metadata"]["project_id"] == str(event.project_id)

    async def test_record_persists_when_mem0_raises(self) -> None:
        """record() must persist to DB even when mem0 raises."""
        persist_fn = AsyncMock()
        mem0 = AsyncMock()
        mem0.add.side_effect = RuntimeError("mem0 down")
        service = FeedbackService(mem0_client=mem0, persist_fn=persist_fn)

        event = _make_event()
        await service.record(event)

        # DB persist still happened
        persist_fn.assert_awaited_once_with(event)
        # mem0 was attempted
        mem0.add.assert_awaited_once()

    async def test_record_with_null_memory_client_still_persists(self) -> None:
        """record() with NullMemoryClient must still persist to DB."""
        persist_fn = AsyncMock()
        null_client = NullMemoryClient()
        service = FeedbackService(mem0_client=null_client, persist_fn=persist_fn)

        event = _make_event()
        await service.record(event)

        # DB persist happened — NullMemoryClient silently succeeds
        persist_fn.assert_awaited_once_with(event)


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
        assert "The sun set over the hills." in text

    def test_reject_action_without_modification(self) -> None:
        event = _make_event(
            action=FeedbackAction.REJECT,
            intent="character",
            suggestion_text="He walked away slowly.",
        )
        text = FeedbackService._translate_to_memory_text(event)

        assert "rejected a character suggestion" in text
        assert "He walked away slowly." in text

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
        assert "Original:" in text
        assert "Their version:" in text
        assert "Hello there." in text
        assert "Hey, how are you?" in text

    def test_long_suggestion_text_is_truncated(self) -> None:
        long_text = "x" * 500
        event = _make_event(
            action=FeedbackAction.ACCEPT,
            suggestion_text=long_text,
        )
        text = FeedbackService._translate_to_memory_text(event)

        # The suggestion text portion should be truncated to 200 chars
        assert len(text) < 500


class TestFeedbackServiceGetHistory:
    """Tests for FeedbackService.get_history()."""

    async def test_get_history_returns_empty_list(self) -> None:
        """get_history() returns empty list (protocol conformance)."""
        service = FeedbackService(
            mem0_client=AsyncMock(),
            persist_fn=AsyncMock(),
        )

        result = await service.get_history(uuid4(), uuid4())
        assert result == []

    async def test_get_history_with_limit_param(self) -> None:
        """get_history() accepts limit parameter without error."""
        service = FeedbackService(
            mem0_client=AsyncMock(),
            persist_fn=AsyncMock(),
        )

        result = await service.get_history(uuid4(), uuid4(), limit=50)
        assert result == []


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
