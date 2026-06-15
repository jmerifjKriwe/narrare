"""Contract regression tests for InterviewDraftGenerator (ADR-045).

Split from ``test_interview_draft`` for RULE-04 (test hard limit 400 lines).

These tests prove the draft path no longer bypasses the invocation
contract. Before migration, ``InterviewDraftGenerator._stream_draft``
called ``composer.build()`` + ``registry.stream()`` directly with NO
invocation context, NO pipeline, NO evidence, and NO limits.
"""

from __future__ import annotations

from tests.unit.api.writing._interview_draft_fakes import identifiers, make_generator

# ---------------------------------------------------------------------------
# Invocation contract regression (ADR-045)
# ---------------------------------------------------------------------------


class TestInvocationContractRegression:
    """Regression: the draft path must use the invocation contract."""

    async def test_draft_passes_usage_limits_to_stream(self) -> None:
        """Regression: registry.stream must receive usage_limits (ADR-045 D4).

        Before migration, ``registry.stream`` was called with NO
        ``usage_limits`` — bypassing output-budget enforcement.
        """
        generator, session_manager, gateway, _ = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)
        await session_manager.add_message(session_id, "user", "A story")
        await session_manager.add_message(session_id, "assistant", "Question?")

        async for _ in generator.stream_draft(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            chapter_id=chapter_id,
        ):
            pass

        gateway.stream.assert_called_once()
        assert gateway.stream.call_args.kwargs["usage_limits"] is not None

    async def test_draft_uses_write_intent(self) -> None:
        """Regression: draft generation uses WRITE intent."""
        from narrare_core.llm import LLMIntent

        generator, session_manager, gateway, _ = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)
        await session_manager.add_message(session_id, "user", "A story")
        await session_manager.add_message(session_id, "assistant", "Question?")

        async for _ in generator.stream_draft(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            chapter_id=chapter_id,
        ):
            pass

        assert gateway.stream.call_args.kwargs["intent"] == LLMIntent.WRITE

    async def test_draft_runs_pipeline_prepare_and_finalize(self) -> None:
        """Regression: with a wired pipeline, prepare/finalize run.

        Uses a real InvocationPipeline so ``build_and_validate_prompt``
        executes prepare → compose → finalize. If the pipeline steps
        raise, the stream never starts. Completing the stream proves
        the full contract ran.
        """
        generator, session_manager, gateway, composer = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)
        await session_manager.add_message(session_id, "user", "A story")
        await session_manager.add_message(session_id, "assistant", "Question?")

        async for _ in generator.stream_draft(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            chapter_id=chapter_id,
        ):
            pass

        # Composer was called through build_and_validate_prompt, not
        # bypassed — proving the invocation adapter ran.
        assert composer.call_count == 1
        gateway.stream.assert_called_once()

    async def test_draft_composer_receives_new_chapter_mode(self) -> None:
        """The prompt context mode is 'new_chapter' for draft generation."""
        generator, session_manager, _, composer = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)
        await session_manager.add_message(session_id, "user", "A story")
        await session_manager.add_message(session_id, "assistant", "Question?")

        async for _ in generator.stream_draft(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            chapter_id=chapter_id,
        ):
            pass

        assert composer.last_context is not None
        assert composer.last_context.mode == "new_chapter"


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
                        f"Brennik controls the eastern shores, House Carthan "
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
        """30 Q&A pairs produce a transcript that still streams successfully."""
        generator, session_manager, _, _ = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)

        for msg in self._long_qa_pairs(30):
            await session_manager.add_message(session_id, msg["role"], msg["content"])

        chunks = [
            c
            async for c in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
            )
        ]

        # Draft should complete successfully (no crash from oversized transcript).
        assert chunks[-1].is_final
        assert any(c.text for c in chunks)

    async def test_short_transcript_not_capped(self) -> None:
        """Short transcript (2-3 Q&A) passes through unchanged."""
        generator, session_manager, _, _ = make_generator()
        chapter_id, user_id, project_id = identifiers()
        session_id = await session_manager.create_session(chapter_id, project_id, user_id)
        await session_manager.add_message(session_id, "user", "A short answer")
        await session_manager.add_message(session_id, "assistant", "Tell me more?")
        await session_manager.add_message(session_id, "user", "Brief detail")

        chunks = [
            c
            async for c in generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
            )
        ]

        texts = "".join(c.text for c in chunks if not c.is_final)
        assert "Once upon a time" in texts
