"""Unit tests for wiki/listeners.py — WikiEventListener event routing.

Tests the event listener's debouncing, UUID extraction, and correct
delegation to wiki task functions. All wiki service interactions are mocked.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

from narrare.wiki.listeners import WikiEventListener
from narrare.wiki.service import APIWikiService
from narrare_core.events.types import DomainEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    event_type: str = "kb.entry.updated",
    **payload: object,
) -> MagicMock:
    """Create a mock DomainEvent with the given event_type and payload."""
    event = MagicMock(spec=DomainEvent)
    event.event_type = event_type
    event.payload = {
        "entity_id": str(uuid.uuid4()),
        "novel_id": str(uuid.uuid4()),
        "chapter_id": str(uuid.uuid4()),
        "prompt_version": "1.0.0",
        **{k: str(v) for k, v in payload.items()},
    }
    return event


def _make_listener() -> WikiEventListener:
    """Create a WikiEventListener with a mock service factory."""
    svc = MagicMock(spec=APIWikiService)
    svc.mark_related_stale = AsyncMock(return_value=0)
    factory = MagicMock(spec=Callable, return_value=svc)
    return WikiEventListener(wiki_service_factory=factory)


# ---------------------------------------------------------------------------
# Tests: on_kb_entry_updated
# ---------------------------------------------------------------------------


class TestOnKbEntryUpdated:
    """on_kb_entry_updated — entity generation + related staleness."""

    async def test_calls_generate_entity(self) -> None:
        """Delegates to run_wiki_generate_entity with correct IDs."""
        listener = _make_listener()
        event = _make_event("kb.entry.updated")
        entity_id = uuid.UUID(event.payload["entity_id"])
        novel_id = uuid.UUID(event.payload["novel_id"])

        with patch("narrare.wiki.listeners.run_wiki_generate_entity") as mock_gen:
            mock_gen.return_value = True
            await listener.on_kb_entry_updated(event)

            mock_gen.assert_called_once()
            call_args = mock_gen.call_args
            assert call_args[0][0] == entity_id
            assert call_args[0][1] == novel_id

    async def test_calls_mark_related_stale(self) -> None:
        """After entity generation, marks related summaries stale."""
        svc = MagicMock(spec=APIWikiService)
        svc.mark_related_stale = AsyncMock(return_value=3)
        factory = MagicMock(spec=Callable, return_value=svc)
        listener = WikiEventListener(wiki_service_factory=factory)
        event = _make_event("kb.entry.updated")
        entity_id = uuid.UUID(event.payload["entity_id"])

        with patch("narrare.wiki.listeners.run_wiki_generate_entity"):
            await listener.on_kb_entry_updated(event)

            svc.mark_related_stale.assert_called_once_with(entity_id)

    async def test_skips_on_invalid_payload(self) -> None:
        """Does nothing when entity_id is missing from payload."""
        listener = _make_listener()
        event = _make_event("kb.entry.updated")
        event.payload = {"novel_id": str(uuid.uuid4())}  # no entity_id

        with patch("narrare.wiki.listeners.run_wiki_generate_entity") as mock_gen:
            await listener.on_kb_entry_updated(event)
            mock_gen.assert_not_called()

    async def test_skips_on_invalid_uuid(self) -> None:
        """Does nothing when entity_id is not a valid UUID."""
        listener = _make_listener()
        event = _make_event("kb.entry.updated", entity_id="not-a-uuid")

        with patch("narrare.wiki.listeners.run_wiki_generate_entity") as mock_gen:
            await listener.on_kb_entry_updated(event)
            mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: on_chapter_finalized
# ---------------------------------------------------------------------------


class TestOnChapterFinalized:
    """on_chapter_finalized — chapter wiki generation."""

    async def test_calls_generate_chapter(self) -> None:
        """Delegates to run_wiki_generate_chapter with correct IDs."""
        listener = _make_listener()
        event = _make_event("chapter.finalized")
        chapter_id = uuid.UUID(event.payload["chapter_id"])
        novel_id = uuid.UUID(event.payload["novel_id"])

        with patch("narrare.wiki.listeners.run_wiki_generate_chapter") as mock_gen:
            mock_gen.return_value = True
            await listener.on_chapter_finalized(event)

            mock_gen.assert_called_once()
            call_args = mock_gen.call_args
            assert call_args[0][0] == chapter_id
            assert call_args[0][1] == novel_id

    async def test_skips_on_missing_chapter_id(self) -> None:
        """Does nothing when chapter_id is missing."""
        listener = _make_listener()
        event = _make_event("chapter.finalized")
        event.payload = {"novel_id": str(uuid.uuid4())}

        with patch("narrare.wiki.listeners.run_wiki_generate_chapter") as mock_gen:
            await listener.on_chapter_finalized(event)
            mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: on_wiki_prompt_changed
# ---------------------------------------------------------------------------


class TestOnWikiPromptChanged:
    """on_wiki_prompt_changed — mark all summaries stale."""

    async def test_calls_mark_all_stale(self) -> None:
        """Delegates to run_wiki_mark_all_stale with novel_id and version."""
        listener = _make_listener()
        event = _make_event("wiki.prompt.changed", prompt_version="2.0.0")
        novel_id = uuid.UUID(event.payload["novel_id"])

        with patch("narrare.wiki.listeners.run_wiki_mark_all_stale") as mock_mark:
            mock_mark.return_value = 5
            await listener.on_wiki_prompt_changed(event)

            mock_mark.assert_called_once()
            call_args = mock_mark.call_args
            assert call_args[0][0] == novel_id
            assert call_args[0][1] == "2.0.0"

    async def test_skips_on_missing_novel_id(self) -> None:
        """Does nothing when novel_id is missing."""
        listener = _make_listener()
        event = _make_event("wiki.prompt.changed")
        event.payload = {"prompt_version": "2.0.0"}

        with patch("narrare.wiki.listeners.run_wiki_mark_all_stale") as mock_mark:
            await listener.on_wiki_prompt_changed(event)
            mock_mark.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: on_wiki_sync_requested
# ---------------------------------------------------------------------------


class TestOnWikiSyncRequested:
    """on_wiki_sync_requested — entity wiki generation trigger."""

    async def test_calls_generate_entity(self) -> None:
        """Delegates to run_wiki_generate_entity."""
        listener = _make_listener()
        event = _make_event("wiki.sync.requested")
        entity_id = uuid.UUID(event.payload["entity_id"])
        novel_id = uuid.UUID(event.payload["novel_id"])

        with patch("narrare.wiki.listeners.run_wiki_generate_entity") as mock_gen:
            mock_gen.return_value = True
            await listener.on_wiki_sync_requested(event)

            mock_gen.assert_called_once()
            call_args = mock_gen.call_args
            assert call_args[0][0] == entity_id
            assert call_args[0][1] == novel_id

    async def test_skips_on_invalid_payload(self) -> None:
        """Does nothing when entity_id is missing from payload."""
        listener = _make_listener()
        event = _make_event("wiki.sync.requested")
        event.payload = {"novel_id": str(uuid.uuid4())}  # no entity_id

        with patch("narrare.wiki.listeners.run_wiki_generate_entity") as mock_gen:
            await listener.on_wiki_sync_requested(event)
            mock_gen.assert_not_called()

    async def test_skips_on_invalid_uuid(self) -> None:
        """Does nothing when entity_id is not a valid UUID."""
        listener = _make_listener()
        event = _make_event("wiki.sync.requested", entity_id="not-a-uuid")

        with patch("narrare.wiki.listeners.run_wiki_generate_entity") as mock_gen:
            await listener.on_wiki_sync_requested(event)
            mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: Debouncing
# ---------------------------------------------------------------------------


class TestDebouncing:
    """WikiEventListener._is_debounced — suppresses rapid-fire events."""

    def test_first_event_is_not_debounced(self) -> None:
        """First occurrence of an event type passes through."""
        listener = _make_listener()
        assert listener._is_debounced("kb.entry.updated", "abc") is False

    def test_rapid_second_event_is_debounced(self) -> None:
        """Same event type + entity within debounce window is suppressed."""
        listener = _make_listener()
        listener._is_debounced("kb.entry.updated", "abc")
        assert listener._is_debounced("kb.entry.updated", "abc") is True

    def test_different_entity_is_not_debounced(self) -> None:
        """Different entity ID for the same event type is not suppressed."""
        listener = _make_listener()
        listener._is_debounced("kb.entry.updated", "abc")
        assert listener._is_debounced("kb.entry.updated", "xyz") is False

    async def test_debounced_event_skips_generate(self) -> None:
        """Debounced on_kb_entry_updated does not call run_wiki_generate_entity."""
        listener = _make_listener()
        event = _make_event("kb.entry.updated")

        # First call goes through.
        with patch("narrare.wiki.listeners.run_wiki_generate_entity") as mock_gen:
            await listener.on_kb_entry_updated(event)
            assert mock_gen.call_count == 1

        # Second call with same event is debounced.
        with patch("narrare.wiki.listeners.run_wiki_generate_entity") as mock_gen:
            await listener.on_kb_entry_updated(event)
            mock_gen.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: Graceful failure (RULE-11)
# ---------------------------------------------------------------------------


class TestGracefulFailure:
    """Event listeners never propagate exceptions (RULE-11)."""

    async def test_entity_generation_failure_does_not_raise(self) -> None:
        """on_kb_entry_updated swallows exceptions from generate_entity."""
        listener = _make_listener()
        event = _make_event("kb.entry.updated")

        with patch(
            "narrare.wiki.listeners.run_wiki_generate_entity",
            side_effect=RuntimeError("LLM down"),
        ):
            # Should NOT raise — graceful degradation.
            await listener.on_kb_entry_updated(event)

    async def test_mark_related_stale_failure_does_not_raise(self) -> None:
        """on_kb_entry_updated swallows exceptions from mark_related_stale."""
        svc = MagicMock(spec=APIWikiService)
        svc.mark_related_stale = AsyncMock(side_effect=RuntimeError("DB error"))
        factory = MagicMock(spec=Callable, return_value=svc)
        listener = WikiEventListener(wiki_service_factory=factory)
        event = _make_event("kb.entry.updated")

        with patch("narrare.wiki.listeners.run_wiki_generate_entity"):
            # Should NOT raise.
            await listener.on_kb_entry_updated(event)

    async def test_chapter_finalized_failure_does_not_raise(self) -> None:
        """on_chapter_finalized swallows exceptions."""
        listener = _make_listener()
        event = _make_event("chapter.finalized")

        with patch(
            "narrare.wiki.listeners.run_wiki_generate_chapter",
            side_effect=RuntimeError("LLM down"),
        ):
            await listener.on_chapter_finalized(event)

    async def test_prompt_changed_failure_does_not_raise(self) -> None:
        """on_wiki_prompt_changed swallows exceptions."""
        listener = _make_listener()
        event = _make_event("wiki.prompt.changed")

        with patch(
            "narrare.wiki.listeners.run_wiki_mark_all_stale",
            side_effect=RuntimeError("DB error"),
        ):
            await listener.on_wiki_prompt_changed(event)

    async def test_sync_requested_failure_does_not_raise(self) -> None:
        """on_wiki_sync_requested swallows exceptions."""
        listener = _make_listener()
        event = _make_event("wiki.sync.requested")

        with patch(
            "narrare.wiki.listeners.run_wiki_generate_entity",
            side_effect=RuntimeError("LLM down"),
        ):
            await listener.on_wiki_sync_requested(event)
