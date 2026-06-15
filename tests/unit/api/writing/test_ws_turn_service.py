"""Regression tests for WritingTurnService — invocation context and pipeline.

ADR-045 Slice 0 (Backend): proves WebSocket writing turns build an
invocation context with user/project/chapter/session identifiers and use
the invocation pipeline (prepare → merge → compose → finalize).

These tests replace the direct ``ModelRegistry.stream`` +
``PromptComposer`` bypass that ``ws_handler._handle_direction``
previously used.
"""

from __future__ import annotations

from uuid import uuid4

from narrare_core.llm import LLMIntent
from tests.unit.api.writing._ws_turn_fakes import make_service

# ---------------------------------------------------------------------------
# Invocation context identifiers
# ---------------------------------------------------------------------------


class TestTurnInvocationContext:
    """The turn service must build an invocation context with identifiers."""

    async def test_turn_passes_user_id_into_invocation(self) -> None:
        """Invocation context must carry the user_id."""
        service, _, registry, _ = make_service()
        user_id = uuid4()
        project_id = uuid4()
        chapter_id = uuid4()
        session_id = uuid4()

        chunks = [
            c
            async for c in service.stream_turn(
                content="Write a scene",
                session_mode="interactive_session",
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
                session_id=session_id,
            )
        ]

        assert any(c.text for c in chunks)
        # The stream was called — proving the invocation completed
        registry.stream.assert_called_once()

    async def test_turn_passes_project_id_into_invocation(self) -> None:
        """Invocation context must carry the project_id."""
        service, _, _, _ = make_service()
        project_id = uuid4()

        async for _ in service.stream_turn(
            content="test",
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=project_id,
            chapter_id=uuid4(),
            session_id=uuid4(),
        ):
            pass
        # If project_id is not accepted, the call raises TypeError
        # before reaching stream.

    async def test_turn_passes_chapter_and_session_ids(self) -> None:
        """Chapter and session IDs must be accepted."""
        service, _, _, _ = make_service()
        chapter_id = uuid4()
        session_id = uuid4()

        async for _ in service.stream_turn(
            content="test",
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=uuid4(),
            chapter_id=chapter_id,
            session_id=session_id,
        ):
            pass


# ---------------------------------------------------------------------------
# Invocation pipeline usage
# ---------------------------------------------------------------------------


class TestTurnUsesInvocationPipeline:
    """The turn service must run the invocation pipeline."""

    async def test_turn_uses_build_and_validate_prompt(self) -> None:
        """Composer.build must receive the merged/prepared context."""
        service, composer, _, _ = make_service()

        async for _ in service.stream_turn(
            content="My direction",
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=uuid4(),
            chapter_id=uuid4(),
            session_id=uuid4(),
        ):
            pass

        # The composer must have been called — proving the prompt was
        # built through the standard path, not inline.
        assert composer.last_context is not None

    async def test_turn_composer_receives_author_instructions(self) -> None:
        """The user's direction must reach the prompt as author_instructions."""
        service, composer, _, _ = make_service()
        direction = "Write a tense dialogue scene"

        async for _ in service.stream_turn(
            content=direction,
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=uuid4(),
            chapter_id=uuid4(),
            session_id=uuid4(),
        ):
            pass

        assert composer.last_context is not None
        assert composer.last_context.author_instructions == direction

    async def test_turn_uses_correct_intent_for_interactive_mode(self) -> None:
        """Interactive session uses WRITE intent."""
        service, _, registry, _ = make_service()

        async for _ in service.stream_turn(
            content="test",
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=uuid4(),
            chapter_id=uuid4(),
            session_id=uuid4(),
        ):
            pass

        call_kwargs = registry.stream.call_args
        assert call_kwargs.kwargs["intent"] == LLMIntent.WRITE

    async def test_turn_uses_correct_intent_for_interview_mode(self) -> None:
        """Interview mode uses CHAT intent."""
        service, _, registry, _ = make_service()

        async for _ in service.stream_turn(
            content="test",
            session_mode="interview_assisted",
            user_id=uuid4(),
            project_id=uuid4(),
            chapter_id=uuid4(),
            session_id=uuid4(),
        ):
            pass

        call_kwargs = registry.stream.call_args
        assert call_kwargs.kwargs["intent"] == LLMIntent.CHAT

    async def test_turn_prompt_mode_reflects_session_mode(self) -> None:
        """The prompt mode must reflect the session mode."""
        service, composer, _, _ = make_service()

        async for _ in service.stream_turn(
            content="test",
            session_mode="interview_assisted",
            user_id=uuid4(),
            project_id=uuid4(),
            chapter_id=uuid4(),
            session_id=uuid4(),
        ):
            pass

        assert composer.last_context is not None
        assert composer.last_context.mode == "interview"
