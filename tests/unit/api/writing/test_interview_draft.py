"""Tests for InterviewDraftGenerator — transcript formatting and streaming.

Covers:
- Transcript formatting from conversation history
- ``stream_draft`` yields ``StreamChunk`` instances (transport-agnostic)
- Error handling: session not found, empty transcript, LLM failure

Contract regression tests (limits enforced, pipeline involvement) live
in ``test_interview_draft_contract.py`` (split for RULE-04).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.writing._interview_draft import InterviewDraftGenerator
from narrare_core.shared.errors import WritingError
from tests.unit.api.writing._interview_draft_fakes import identifiers, make_generator

# ---------------------------------------------------------------------------
# Transcript formatting
# ---------------------------------------------------------------------------


class TestTranscriptFormatting:
    """_format_transcript converts conversation history to readable text."""

    def test_format_empty_history(self) -> None:
        """Empty history returns empty string."""
        result = InterviewDraftGenerator._format_transcript([])
        assert result == ""

    def test_format_user_messages(self) -> None:
        """User messages get 'Author:' prefix."""
        history = [{"role": "user", "content": "I want a mystery"}]
        result = InterviewDraftGenerator._format_transcript(history)
        assert "Author: I want a mystery" in result

    def test_format_assistant_messages(self) -> None:
        """Assistant messages get 'Interviewer:' prefix."""
        history = [{"role": "assistant", "content": "What genre?"}]
        result = InterviewDraftGenerator._format_transcript(history)
        assert "Interviewer: What genre?" in result

    def test_format_mixed_messages(self) -> None:
        """Mixed conversation formats correctly with separators."""
        history = [
            {"role": "user", "content": "A dog story"},
            {"role": "assistant", "content": "What kind of dog?"},
            {"role": "user", "content": "A golden retriever"},
        ]
        result = InterviewDraftGenerator._format_transcript(history)
        assert "Author: A dog story" in result
        assert "Interviewer: What kind of dog?" in result
        assert "Author: A golden retriever" in result
        assert result.count("\n\n") == 2

    def test_format_ignores_unknown_roles(self) -> None:
        """Messages with unknown roles are skipped."""
        history = [
            {"role": "system", "content": "You are a helper"},
            {"role": "user", "content": "Hello"},
        ]
        result = InterviewDraftGenerator._format_transcript(history)
        assert "Author: Hello" in result
        assert "system" not in result


# ---------------------------------------------------------------------------
# Draft generation via stream_draft (transport-agnostic)
# ---------------------------------------------------------------------------


class TestStreamDraft:
    """stream_draft yields StreamChunk instances via the invocation contract."""

    async def test_stream_draft_yields_chunks_from_transcript(self) -> None:
        """Valid transcript produces streamed chunks."""
        generator, session_manager, _, _ = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)
        await session_manager.add_message(session_id, "user", "A story about cats")
        await session_manager.add_message(session_id, "assistant", "What happens?")

        chunks = [
            c
            async for c in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
            )
        ]

        texts = [c.text for c in chunks if not c.is_final]
        assert "Once upon a time " in texts
        assert chunks[-1].is_final

    async def test_stream_draft_session_not_found_raises(self) -> None:
        """Missing session raises WritingError."""
        generator, _, _, _ = make_generator()
        chapter_id, user_id, project_id = identifiers()

        with pytest.raises(WritingError, match=r"(?i)not found"):
            async for _ in generator.stream_draft(
                session_id=uuid4(),
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
            ):
                pass

    async def test_stream_draft_empty_transcript_raises(self) -> None:
        """Session with no Q&A raises WritingError about empty answers."""
        generator, session_manager, _, _ = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)

        with pytest.raises(WritingError, match=r"(?i)no interview answers"):
            async for _ in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
            ):
                pass

    async def test_stream_draft_llm_failure_propagates(self) -> None:
        """LLM gateway failure propagates to the consumer (no silent swallow)."""
        from unittest.mock import Mock

        generator, session_manager, gateway, _ = make_generator()
        gateway.stream = Mock(side_effect=RuntimeError("LLM down"))
        chapter_id, user_id, project_id = identifiers()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)
        await session_manager.add_message(session_id, "user", "A story")
        await session_manager.add_message(session_id, "assistant", "Question?")

        with pytest.raises(RuntimeError, match="LLM down"):
            async for _ in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
            ):
                pass

    async def test_stream_draft_has_no_websocket_dependency(self) -> None:
        """stream_draft is transport-agnostic (RULE-12/RULE-13).

        It accepts only identifiers and yields StreamChunk — no WebSocket.
        The caller is responsible for DTO mapping and persistence.
        """
        generator, session_manager, _, _ = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)
        await session_manager.add_message(session_id, "user", "Content")

        # Consume without any WebSocket — proves transport-agnosticism.
        chunks = [
            c
            async for c in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
            )
        ]
        assert any(c.text for c in chunks)
