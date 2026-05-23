"""Tests for InterviewDraftGenerator — interview-assisted draft generation.

Covers:
- Transcript formatting from conversation history
- Draft generation with valid transcript
- Error when session not found
- Error when transcript is empty
- LLM gateway failure during streaming
- Draft persistence (message + prose buffer)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.prompts.context import PromptContext

from typing import Any
from unittest.mock import Mock
from uuid import uuid4

from narrare.writing._interview_draft import InterviewDraftGenerator
from narrare.writing._ws_cache import InMemorySessionCache
from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.writing.session_manager import SessionManager

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockWebSocket:
    """Simplified async WebSocket mock for unit tests."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self._closed = False

    async def accept(self) -> None:
        """Accept the WebSocket connection."""

    async def send_json(self, data: dict[str, Any]) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self._closed = True

    async def receive_text(self) -> str:
        return "{}"

    async def send_text(self, message: str) -> None:
        pass


class _FakeComposer:
    """Stub PromptComposer that returns a fixed prompt."""

    async def build(
        self,
        intent: LLMIntent,
        context: PromptContext,
        *,
        db_content: str | None = None,
        user_prompt: str = "",
    ) -> ComposedPrompt:
        return ComposedPrompt(system="system-prompt", user="user-prompt")


async def _fake_stream_hello(*args: object, **kwargs: object) -> AsyncIterator[StreamChunk]:
    """Yield text chunks then a final chunk."""
    yield StreamChunk(text="Once upon a time ")
    yield StreamChunk(text="there was a dog.", is_final=True, usage=TokenUsage(10, 20, 30))


def _make_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=100,
    )


def _make_generator() -> tuple[InterviewDraftGenerator, SessionManager, Mock]:
    """Create an InterviewDraftGenerator with mock dependencies."""
    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    gateway = Mock()
    gateway.stream = Mock(side_effect=_fake_stream_hello)
    composer = _FakeComposer()
    config = _make_config()

    generator = InterviewDraftGenerator(
        session_manager=session_manager,
        registry=gateway,
        composer=composer,  # type: ignore[assignment]
        config=config,
    )
    return generator, session_manager, gateway


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
# Draft generation
# ---------------------------------------------------------------------------


class TestDraftGeneration:
    """Full draft generation from interview transcript."""

    async def test_generate_with_valid_transcript(self) -> None:
        """Valid transcript produces draft_done with word count."""
        generator, session_manager, _ = _make_generator()
        ws = MockWebSocket()

        # Create session and add Q&A
        chapter_id = uuid4()
        project_id = uuid4()
        user_id = uuid4()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)
        await session_manager.add_message(session_id, "user", "A story about cats")
        await session_manager.add_message(session_id, "assistant", "What happens to the cats?")
        await session_manager.add_message(session_id, "user", "They learn to fly")

        await generator.generate(ws, session_id)  # type: ignore[arg-type]

        # Should have text_chunk(s) and draft_done
        draft_done = [m for m in ws.sent if m["type"] == "draft_done"]
        assert len(draft_done) == 1
        assert draft_done[0]["word_count"] > 0
        assert "Once upon a time" in draft_done[0]["text"]

    async def test_generate_session_not_found(self) -> None:
        """Missing session returns error."""
        generator, _, _ = _make_generator()
        ws = MockWebSocket()

        await generator.generate(ws, uuid4())  # type: ignore[arg-type]

        errors = [m for m in ws.sent if m["type"] == "error"]
        assert len(errors) == 1
        assert "not found" in errors[0]["message"].lower()

    async def test_generate_empty_transcript(self) -> None:
        """Session with no Q&A returns error about empty answers."""
        generator, session_manager, _ = _make_generator()
        ws = MockWebSocket()

        session_id = await session_manager.create_session(uuid4(), uuid4(), uuid4())
        # Don't add any messages

        await generator.generate(ws, session_id)  # type: ignore[arg-type]

        errors = [m for m in ws.sent if m["type"] == "error"]
        assert len(errors) == 1
        assert "no interview answers" in errors[0]["message"].lower()

    async def test_generate_llm_failure_sends_error(self) -> None:
        """LLM gateway failure sends error message."""
        generator, session_manager, gateway = _make_generator()
        gateway.stream = Mock(side_effect=RuntimeError("LLM down"))
        ws = MockWebSocket()

        session_id = await session_manager.create_session(uuid4(), uuid4(), uuid4())
        await session_manager.add_message(session_id, "user", "A story")
        await session_manager.add_message(session_id, "assistant", "Question?")

        await generator.generate(ws, session_id)  # type: ignore[arg-type]

        errors = [m for m in ws.sent if m["type"] == "error"]
        assert len(errors) == 1
        assert "draft generation failed" in errors[0]["message"].lower()

    async def test_generate_persists_to_session(self) -> None:
        """Generated draft is added to conversation history and prose buffer."""
        generator, session_manager, _ = _make_generator()
        ws = MockWebSocket()

        session_id = await session_manager.create_session(uuid4(), uuid4(), uuid4())
        await session_manager.add_message(session_id, "user", "A story")
        await session_manager.add_message(session_id, "assistant", "Question?")

        await generator.generate(ws, session_id)  # type: ignore[arg-type]

        # Verify draft was saved to session
        state = await session_manager.get_session(session_id)
        assert state is not None
        # Should have: user message, assistant question, + generated draft
        assert len(state.conversation_history) == 3
        assert state.conversation_history[-1]["role"] == "assistant"
        assert state.prose_buffer  # non-empty


# ---------------------------------------------------------------------------
# Token-budget enforcement
# ---------------------------------------------------------------------------


class TestInterviewDraftTokenBudget:
    """Token-budget enforcement for interview transcript capping."""

    @staticmethod
    def _long_qa_pairs(count: int) -> list[dict[str, str]]:
        """Build *count* Q&A pairs with deliberately verbose answers."""
        history: list[dict[str, str]] = []
        for i in range(count):
            history.append(
                {
                    "role": "assistant",
                    "content": (
                        f"Question {i}: Tell me about the political landscape "
                        f"of the kingdom and how the various noble houses "
                        f"interact with each other?"
                    ),
                }
            )
            history.append(
                {
                    "role": "user",
                    "content": (
                        f"Answer {i}: The kingdom is divided into five major "
                        f"houses, each controlling vast territories and armies. "
                        f"House Aldric rules the northern mountains, House "
                        f"Brennick controls the eastern shores, House Carthan "
                        f"holds the central plains, House Delvane governs the "
                        f"southern forests, and House Edwyr maintains the "
                        f"western deserts. Their alliances shift with the "
                        f"seasons, but currently Aldric and Carthan are united "
                        f"against Brennick's expansionist policies."
                    ),
                }
            )
        return history

    async def test_long_transcript_capped_to_budget(self) -> None:
        """30 Q&A pairs produce a transcript that still generates successfully."""
        generator, session_manager, _ = _make_generator()
        ws = MockWebSocket()

        session_id = await session_manager.create_session(uuid4(), uuid4(), uuid4())

        # Add 30 verbose Q&A pairs — would be thousands of tokens uncapped.
        for msg in self._long_qa_pairs(30):
            await session_manager.add_message(session_id, msg["role"], msg["content"])

        await generator.generate(ws, session_id)  # type: ignore[arg-type]

        # Draft should complete successfully (no crash).
        draft_done = [m for m in ws.sent if m["type"] == "draft_done"]
        assert len(draft_done) == 1
        assert draft_done[0]["word_count"] > 0

    async def test_short_transcript_not_capped(self) -> None:
        """Short transcript (2-3 Q&A) passes through unchanged."""
        generator, session_manager, _ = _make_generator()
        ws = MockWebSocket()

        session_id = await session_manager.create_session(uuid4(), uuid4(), uuid4())
        await session_manager.add_message(session_id, "user", "A short answer")
        await session_manager.add_message(session_id, "assistant", "Tell me more?")
        await session_manager.add_message(session_id, "user", "Brief detail")

        await generator.generate(ws, session_id)  # type: ignore[arg-type]

        draft_done = [m for m in ws.sent if m["type"] == "draft_done"]
        assert len(draft_done) == 1
        assert "Once upon a time" in draft_done[0]["text"]
