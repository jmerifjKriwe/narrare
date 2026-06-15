"""Tests for WritingTurnService — budget enforcement and stream output.

Split from ``test_ws_turn_service`` for RULE-04 (test hard limit 300 lines).
"""

from __future__ import annotations

from uuid import uuid4

from pydantic_ai.usage import UsageLimits

from tests.unit.api.writing._ws_turn_fakes import make_service

# ---------------------------------------------------------------------------
# Run-limit enforcement
# ---------------------------------------------------------------------------


class TestTurnBudgetEnforcement:
    """The turn service must enforce output budgets via resolved limits."""

    async def test_turn_passes_usage_limits_to_stream(self) -> None:
        """Stream must receive usage_limits so the budget is enforced.

        The ModelRegistryProtocol.stream() contract accepts ``usage_limits``
        (a pydantic-ai ``UsageLimits``), not the full ``ResolvedRunLimits``.
        """
        service, _, registry, _ = make_service(token_profile="balanced")

        async for _ in service.stream_turn(
            content="test",
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=uuid4(),
            chapter_id=uuid4(),
            session_id=uuid4(),
        ):
            pass

        call_kwargs = registry.stream.call_args.kwargs
        assert "usage_limits" in call_kwargs
        limits = call_kwargs["usage_limits"]
        assert limits is not None
        assert isinstance(limits, UsageLimits)
        assert limits.output_tokens_limit is not None

    async def test_turn_usage_limits_carry_output_budget(self) -> None:
        """The resolved usage_limits must carry an output token budget."""
        service, _, registry, _ = make_service(token_profile="long_texts")

        async for _ in service.stream_turn(
            content="test",
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=uuid4(),
            chapter_id=uuid4(),
            session_id=uuid4(),
        ):
            pass

        call_kwargs = registry.stream.call_args.kwargs
        limits: UsageLimits = call_kwargs["usage_limits"]
        assert limits.output_tokens_limit is not None
        assert limits.output_tokens_limit > 0

    async def test_turn_limits_reflect_config_profile(self) -> None:
        """The usage_limits output budget should reflect the config token profile.

        With ``token_profile="comprehensive"``, ``resolve_output_limit()``
        returns 16000 (from ``PROFILE_OUTPUT_LIMITS``), so the stream
        receives ``usage_limits`` with ``output_tokens_limit=16000``.
        """
        service, _, registry, _ = make_service(token_profile="comprehensive")

        async for _ in service.stream_turn(
            content="test",
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=uuid4(),
            chapter_id=uuid4(),
            session_id=uuid4(),
        ):
            pass

        call_kwargs = registry.stream.call_args.kwargs
        limits: UsageLimits = call_kwargs["usage_limits"]
        assert limits.output_tokens_limit == 16000

    async def test_turn_limits_apply_when_no_profile(self) -> None:
        """Limits are enforced even without a token profile (from max_tokens)."""
        service, _, registry, _ = make_service(token_profile=None)

        async for _ in service.stream_turn(
            content="test",
            session_mode="interactive_session",
            user_id=uuid4(),
            project_id=uuid4(),
            chapter_id=uuid4(),
            session_id=uuid4(),
        ):
            pass

        call_kwargs = registry.stream.call_args.kwargs
        limits: UsageLimits = call_kwargs["usage_limits"]
        assert limits.output_tokens_limit is not None


# ---------------------------------------------------------------------------
# Stream output
# ---------------------------------------------------------------------------


class TestTurnStreamOutput:
    """The turn service yields StreamChunks correctly."""

    async def test_turn_yields_text_chunks_then_final(self) -> None:
        """Non-final chunks carry text; final chunk carries usage."""
        service, _, _, _ = make_service()

        chunks = [
            c
            async for c in service.stream_turn(
                content="test",
                session_mode="interactive_session",
                user_id=uuid4(),
                project_id=uuid4(),
                chapter_id=uuid4(),
                session_id=uuid4(),
            )
        ]

        text_chunks = [c for c in chunks if not c.is_final]
        final = [c for c in chunks if c.is_final]
        assert len(text_chunks) >= 1
        assert len(final) == 1
        assert final[0].usage is not None
        assert final[0].usage.total_tokens == 30

    async def test_turn_full_text_is_concatenated(self) -> None:
        """The full text equals all chunk text concatenated."""
        service, _, _, _ = make_service()

        chunks = [
            c
            async for c in service.stream_turn(
                content="test",
                session_mode="interactive_session",
                user_id=uuid4(),
                project_id=uuid4(),
                chapter_id=uuid4(),
                session_id=uuid4(),
            )
        ]

        full = "".join(c.text for c in chunks)
        assert "Hello" in full
        assert "world" in full
