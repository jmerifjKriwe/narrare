"""Tests for ai_assist domain Protocol + Pydantic schemas (RULE-03, RULE-13).

Phase 4 Task 12: contracts + schemas land BEFORE the service (Task 13) and
router (Task 14). The Protocol has BOTH run() and stream() per ADR-065.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.ai_assist.contracts import DialogueCoachServiceProtocol
from narrare.ai_assist.schemas import (
    DialogueCoachRequest,
    DialogueCoachResponse,
    DialogueCoachStreamEvent,
)


class _FakeService:
    """Complete DialogueCoachServiceProtocol for tests."""

    async def run(
        self,
        chapter_id: object,
        user_id: object,
        request: DialogueCoachRequest,
    ) -> DialogueCoachResponse:
        return DialogueCoachResponse(
            chapter_id=str(chapter_id),
            mode=request.mode,
            issues=[],
            adaptive_summary="",
        )

    async def stream(
        self,
        chapter_id: object,
        user_id: object,
        request: DialogueCoachRequest,
    ):
        yield DialogueCoachStreamEvent(event="done", is_final=True)


class TestDialogueCoachServiceProtocol:
    """Protocol has BOTH run() and stream() (ADR-065 / RULE-13)."""

    def test_fake_satisfies_protocol(self) -> None:
        assert isinstance(_FakeService(), DialogueCoachServiceProtocol)

    def test_service_with_only_run_does_not_satisfy(self) -> None:
        class OnlyRun:
            async def run(self, *args: object) -> DialogueCoachResponse: ...

        assert not isinstance(OnlyRun(), DialogueCoachServiceProtocol)

    def test_service_with_only_stream_does_not_satisfy(self) -> None:
        class OnlyStream:
            async def stream(self, *args: object) -> None: ...

        assert not isinstance(OnlyStream(), DialogueCoachServiceProtocol)


class TestDialogueCoachRequest:
    """Request body schema for POST /ai-assist/dialogue-coach/{chapter_id}."""

    def test_analyze_mode(self) -> None:
        req = DialogueCoachRequest(
            selection_text='"Hello," she said.',
            mode="analyze",
        )
        assert req.mode == "analyze"
        assert req.selection_text == '"Hello," she said.'

    def test_improve_mode(self) -> None:
        req = DialogueCoachRequest(
            selection_text='"Hello."',
            mode="improve",
        )
        assert req.mode == "improve"

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValueError):
            DialogueCoachRequest(selection_text="x", mode="bad")  # type: ignore[arg-type]

    def test_empty_selection_rejected(self) -> None:
        with pytest.raises(ValueError):
            DialogueCoachRequest(selection_text="", mode="analyze")


class TestDialogueCoachResponse:
    """Non-streaming response."""

    def test_minimal(self) -> None:
        r = DialogueCoachResponse(
            chapter_id=str(uuid4()),
            mode="analyze",
            issues=[],
            adaptive_summary="",
        )
        assert r.issues == []


class TestDialogueCoachStreamEvent:
    """SSE event types match the established analysis SSE pattern."""

    def test_progress_event(self) -> None:
        e = DialogueCoachStreamEvent(event="progress", progress="Analysing…")
        assert e.event == "progress"
        assert e.is_final is False

    def test_result_event(self) -> None:
        r = DialogueCoachResponse(
            chapter_id=str(uuid4()),
            mode="analyze",
            issues=[],
            adaptive_summary="",
        )
        e = DialogueCoachStreamEvent(event="result", result=r)
        assert e.event == "result"

    def test_done_event(self) -> None:
        e = DialogueCoachStreamEvent(event="done", is_final=True)
        assert e.is_final is True

    def test_error_event(self) -> None:
        e = DialogueCoachStreamEvent(event="error", error="boom", is_final=True)
        assert e.event == "error"
        assert e.is_final is True
