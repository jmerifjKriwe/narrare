"""Tests for _ws_session_handlers — transport-specific WebSocket DTO handlers.

Covers ``handle_feedback`` and ``handle_save`` for all success and error
paths.  These functions contain no LLM or prompt logic — they are thin
WebSocket message handlers extracted for RULE-04 compliance.

Uses ``AsyncMock`` with ``spec=WebSocket`` / ``spec=SessionManager`` for
type-safe mocking (RULE-TEST-01).
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import WebSocket

from narrare.writing._ws_session_handlers import handle_feedback, handle_save
from narrare_core.writing.session_manager import SessionManager


def _ws() -> AsyncMock:
    """Create a spec'd WebSocket mock for handler testing."""
    return AsyncMock(spec=WebSocket)


def _session_manager() -> AsyncMock:
    """Create a spec'd SessionManager mock."""
    mgr = AsyncMock(spec=SessionManager)
    mgr.append_prose = AsyncMock()
    mgr.save_to_chapter = AsyncMock()
    return mgr


class TestHandleFeedback:
    """handle_feedback — user accept/reject on generated text."""

    # ------------------------------------------------------------------
    # Accept path
    # ------------------------------------------------------------------

    async def test_accept_with_valid_text_appends_prose_and_sends_ack(self) -> None:
        """action='accept' with non-empty text calls append_prose and sends ack."""
        ws = _ws()
        session_id: UUID = uuid4()
        mgr = _session_manager()
        data: dict[str, object] = {"action": "accept", "text": "This is accepted text."}

        await handle_feedback(ws, session_id, data, mgr)

        mgr.append_prose.assert_awaited_once_with(session_id, "This is accepted text.")
        ws.send_json.assert_awaited_once_with({"type": "feedback_acknowledged", "action": "accept"})

    async def test_accept_with_empty_text_sends_error(self) -> None:
        """action='accept' with empty text must not append prose."""
        ws = _ws()
        session_id = uuid4()
        mgr = _session_manager()
        data: dict[str, object] = {"action": "accept", "text": ""}

        await handle_feedback(ws, session_id, data, mgr)

        mgr.append_prose.assert_not_awaited()
        ws.send_json.assert_awaited_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "error"

    async def test_accept_with_whitespace_text_sends_error(self) -> None:
        """action='accept' with whitespace-only text must not append prose."""
        ws = _ws()
        session_id = uuid4()
        mgr = _session_manager()
        data: dict[str, object] = {"action": "accept", "text": "   \n  "}

        await handle_feedback(ws, session_id, data, mgr)

        mgr.append_prose.assert_not_awaited()
        ws.send_json.assert_awaited_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "error"

    async def test_accept_with_non_string_text_sends_error(self) -> None:
        """action='accept' with non-str text must not append prose."""
        ws = _ws()
        session_id = uuid4()
        mgr = _session_manager()
        data: dict[str, object] = {"action": "accept", "text": 123}

        await handle_feedback(ws, session_id, data, mgr)

        mgr.append_prose.assert_not_awaited()
        ws.send_json.assert_awaited_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "error"

    # ------------------------------------------------------------------
    # Reject path
    # ------------------------------------------------------------------

    async def test_reject_sends_rejection_ack(self) -> None:
        """action='reject' sends feedback_acknowledged with action=reject."""
        ws = _ws()
        session_id = uuid4()
        mgr = _session_manager()
        data: dict[str, object] = {"action": "reject"}

        await handle_feedback(ws, session_id, data, mgr)

        mgr.append_prose.assert_not_awaited()
        ws.send_json.assert_awaited_once_with({"type": "feedback_acknowledged", "action": "reject"})

    # ------------------------------------------------------------------
    # Invalid action path
    # ------------------------------------------------------------------

    async def test_invalid_action_sends_error(self) -> None:
        """Unknown action sends error message to client with action name."""
        ws = _ws()
        session_id = uuid4()
        mgr = _session_manager()
        data: dict[str, object] = {"action": "unknown_action"}

        await handle_feedback(ws, session_id, data, mgr)

        mgr.append_prose.assert_not_awaited()
        ws.send_json.assert_awaited_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "error"
        assert "unknown_action" in payload["message"]

    async def test_missing_action_sends_error(self) -> None:
        """Missing 'action' key defaults to empty string and triggers error."""
        ws = _ws()
        session_id = uuid4()
        mgr = _session_manager()
        data: dict[str, object] = {}

        await handle_feedback(ws, session_id, data, mgr)

        mgr.append_prose.assert_not_awaited()
        ws.send_json.assert_awaited_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "error"


class TestHandleSave:
    """handle_save — save prose buffer to chapter."""

    # ------------------------------------------------------------------
    # Success path
    # ------------------------------------------------------------------

    async def test_save_success_returns_content_with_word_count(self) -> None:
        """Successful save returns content and word_count."""
        ws = _ws()
        session_id = uuid4()
        mgr = _session_manager()
        mgr.save_to_chapter.return_value = "Hello world, this is a test."

        await handle_save(ws, session_id, mgr)

        mgr.save_to_chapter.assert_awaited_once_with(session_id)
        ws.send_json.assert_awaited_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "saved"
        assert payload["content"] == "Hello world, this is a test."
        assert payload["word_count"] == 6

    async def test_save_with_empty_content_returns_zero_word_count(self) -> None:
        """Empty string content returns word_count of 0."""
        ws = _ws()
        session_id = uuid4()
        mgr = _session_manager()
        mgr.save_to_chapter.return_value = ""

        await handle_save(ws, session_id, mgr)

        ws.send_json.assert_awaited_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["word_count"] == 0

    async def test_save_with_single_word(self) -> None:
        """Single word content returns word_count of 1."""
        ws = _ws()
        session_id = uuid4()
        mgr = _session_manager()
        mgr.save_to_chapter.return_value = "Hello"

        await handle_save(ws, session_id, mgr)

        ws.send_json.assert_awaited_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["word_count"] == 1

    # ------------------------------------------------------------------
    # Error path
    # ------------------------------------------------------------------

    async def test_save_value_error_sends_error(self) -> None:
        """ValueError from save_to_chapter sends error to client."""
        ws = _ws()
        session_id = uuid4()
        mgr = _session_manager()
        mgr.save_to_chapter.side_effect = ValueError("Prose buffer is empty — nothing to save.")

        await handle_save(ws, session_id, mgr)

        mgr.save_to_chapter.assert_awaited_once_with(session_id)
        ws.send_json.assert_awaited_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "error"
        assert "Prose buffer is empty" in payload["message"]
