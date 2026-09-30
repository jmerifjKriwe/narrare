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

    async def test_record_degrades_gracefully_on_vector_store_error(self) -> None:
        """record() must not propagate mem0 >=2.2.1 ``VectorStoreError`` from add().

        mem0 2.2.1 changed ``add()`` to raise ``VectorStoreError`` when NONE of
        the extracted memories could be inserted into the vector store
        (previously it reported never-stored memories as successful ADD
        events). Regression pin for the mem0ai 2.0.18 -> 2.2.1 upgrade: the
        exception must be contained at the service boundary so the request
        path (DB audit trail) stays intact (RULE-11 graceful degradation).

        Uses a local ``MemoryError`` subclass mirroring the real
        ``mem0.exceptions.VectorStoreError`` hierarchy. mem0 is not imported
        here because RULE-08 confines mem0 imports to ``core/memory/``.
        """

        class _VectorStoreError(MemoryError):
            """Stub mirroring ``mem0.exceptions.VectorStoreError(MemoryError)``."""

        persist_fn = AsyncMock()
        mem0 = AsyncMock()
        mem0.add.side_effect = _VectorStoreError(
            "Failed to insert any of the 2 extracted memories into the vector store"
        )
        service = FeedbackService(mem0_client=mem0, persist_fn=persist_fn)

        event = _make_event()
        # Must not raise — the vector-store failure is contained as a warning.
        await service.record(event)

        # DB audit-trail persist still happened (before the mem0 forward)
        persist_fn.assert_awaited_once_with(event)
        # The failing mem0 add() was attempted — its error did not leak upward
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

    async def test_record_forwards_source_type_to_mem0_metadata(self) -> None:
        """record() must propagate context['source_type'] to mem0 metadata.

        Enables preference routing by source (CR-AUFG-07-24). Privacy-safe:
        source_type is a taxonomy tag, never raw prose.
        """
        persist_fn = AsyncMock()
        mem0 = AsyncMock()
        service = FeedbackService(mem0_client=mem0, persist_fn=persist_fn)

        event = _make_event(context={"source_type": "chat_message"})
        await service.record(event)

        call_kwargs = mem0.add.call_args[1]
        assert call_kwargs["metadata"]["source_type"] == "chat_message"

    async def test_record_mem0_metadata_source_type_none_when_absent(self) -> None:
        """When context has no source_type, metadata carries None explicitly.

        Back-compat: the metadata key is always present so downstream consumers
        can rely on a stable schema.
        """
        persist_fn = AsyncMock()
        mem0 = AsyncMock()
        service = FeedbackService(mem0_client=mem0, persist_fn=persist_fn)

        event = _make_event(context={})
        await service.record(event)

        call_kwargs = mem0.add.call_args[1]
        assert call_kwargs["metadata"]["source_type"] is None

    async def test_record_does_not_forward_raw_source_id_to_mem0(self) -> None:
        """record() must not leak raw source_id or raw suggestion text to mem0.

        The API boundary may accept a client-local source_id, but Core's mem0
        boundary stays privacy-safe: it forwards the resolved suggestion_id and
        taxonomy source_type only, never the raw source_id or suggestion prose.
        """
        persist_fn = AsyncMock()
        mem0 = AsyncMock()
        service = FeedbackService(mem0_client=mem0, persist_fn=persist_fn)
        raw_source_id = "editor-selection-raw-source-id-42"
        raw_suggestion_text = "Secret draft prose that must not reach mem0."

        event = _make_event(
            suggestion_text=raw_suggestion_text,
            context={
                "source_id": raw_source_id,
                "source_type": "editor_annotation",
            },
        )
        await service.record(event)

        call_kwargs = mem0.add.call_args[1]
        assert call_kwargs["metadata"]["suggestion_id"] == str(event.suggestion_id)
        assert "source_id" not in call_kwargs["metadata"]
        assert raw_source_id not in str(call_kwargs["metadata"])
        assert raw_source_id not in call_kwargs["messages"]
        assert raw_suggestion_text not in str(call_kwargs["metadata"])
        assert raw_suggestion_text not in call_kwargs["messages"]


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
