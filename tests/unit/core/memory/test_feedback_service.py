"""Tests for memory/feedback_service.py — FeedbackService.

Service-behavior tests (record, get_history, unknown-action fallback).
Translation-logic tests live in ``test_feedback_service_translation.py``.

See: ADR-045 Decision 8, CONSTRAINTS.md RULE-08/RULE-22.
"""

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


class TestFeedbackServiceUnknownAction:
    """Tests for the else-branch fallback in _translate_to_memory_text()."""

    def test_unknown_action_falls_to_generic_text(self) -> None:
        """A non-enum action falls back to the generic 'interacted with' text."""
        event = _make_event(
            action="unknown",  # type: ignore[arg-type]
            intent="rewrite",
            suggestion_text="Some text.",
        )
        text = FeedbackService._translate_to_memory_text(event)
        assert "interacted with a rewrite suggestion" in text
        # The else branch does not include suggestion_text
        assert "User interacted with" in text
