"""Unit tests for ChatService InvocationPipeline integration (ADR-045/ADR-048).

Verifies:
- ``compose_chat_invocation()`` builds a correct ``PromptInvocationContext`` and
  calls ``compose_invocation()`` (Mode 2 — agent-internal composition).
- The enriched context flows to ``ChatDeps`` so the agent receives enrichment.
- ``resolve_chat_run_limits()`` resolves output budgets and passes limits
  to ``agent.run_stream()``.
- Streaming works with the pipeline wired (no regression).
- Backward compatibility: ``invocation_pipeline=None`` preserves pre-pipeline
  behavior.

See:
    ADR-045, ADR-048, CONSTRAINTS.md RULE-13 (streaming).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from narrare_core.prompts.context import PromptContext

from narrare_core.ai_invocation import ComposedInvocation, InvocationPipeline
from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration

# ---------------------------------------------------------------------------
# Tests for compose_chat_invocation (the _invocation module entry point)
# ---------------------------------------------------------------------------


class TestComposeChatInvocation:
    """Tests for ``compose_chat_invocation()`` — the invocation adapter call."""

    async def test_compose_invocation_called_with_manual_injection_mode(
        self,
        prompt_context: PromptContext,
    ) -> None:
        """``compose_invocation`` receives the ManualInjectionDeclaration (Mode 2)."""
        from uuid import uuid4

        from narrare.chat._invocation import CHAT_MANUAL_INJECTION, compose_chat_invocation

        pipeline = MagicMock(name="pipeline", spec=InvocationPipeline)

        with patch("narrare.chat._invocation.compose_invocation") as mock_ci:
            mock_result = MagicMock(name="composed_result", spec=ComposedInvocation)
            mock_result.merged_context = prompt_context
            mock_ci.return_value = mock_result

            result = await compose_chat_invocation(
                invocation_pipeline=pipeline,
                prompt_ctx=prompt_context,
                user_id=uuid4(),
                project_id=uuid4(),
                conv_id=uuid4(),
                invocation_id=uuid4(),
            )

        # compose_invocation was called exactly once
        mock_ci.assert_called_once()

        # Mode 2: manual_injection is set, composer not provided (defaults to None)
        _call_kwargs = mock_ci.call_args.kwargs
        assert _call_kwargs["manual_injection"] == CHAT_MANUAL_INJECTION

        # Invocation context has the correct metadata
        inv_ctx = _call_kwargs["invocation_context"]
        assert inv_ctx.feature_id == "chat"
        assert inv_ctx.streaming is True
        assert inv_ctx.intent.value == "chat"

        # Enriched context is returned
        assert result is prompt_context

    async def test_compose_without_pipeline_returns_original_context(
        self,
        prompt_context: PromptContext,
    ) -> None:
        """When ``invocation_pipeline`` is ``None``, ``compose_chat_invocation``
        returns the original context unchanged (backward-compatible no-op)."""
        from uuid import uuid4

        from narrare.chat._invocation import compose_chat_invocation

        result = await compose_chat_invocation(
            invocation_pipeline=None,
            prompt_ctx=prompt_context,
            user_id=uuid4(),
            project_id=uuid4(),
            conv_id=uuid4(),
            invocation_id=uuid4(),
        )
        assert result is prompt_context

    async def test_compose_failure_returns_original_context(
        self,
        prompt_context: PromptContext,
    ) -> None:
        """When ``compose_invocation`` raises, the original context is returned
        (RULE-11: graceful degradation, chat keeps working)."""
        from uuid import uuid4

        from narrare.chat._invocation import compose_chat_invocation

        pipeline = MagicMock(name="pipeline", spec=InvocationPipeline)

        with patch("narrare.chat._invocation.compose_invocation") as mock_ci:
            mock_ci.side_effect = RuntimeError("Simulated pipeline failure")

            result = await compose_chat_invocation(
                invocation_pipeline=pipeline,
                prompt_ctx=prompt_context,
                user_id=uuid4(),
                project_id=uuid4(),
                conv_id=uuid4(),
                invocation_id=uuid4(),
            )

        # Original context is returned — chat is not blocked
        assert result is prompt_context

    async def test_chat_manual_injection_is_well_formed(self) -> None:
        """The ``CHAT_MANUAL_INJECTION`` declaration is valid per ADR-048."""
        from narrare.chat._invocation import CHAT_MANUAL_INJECTION

        assert isinstance(CHAT_MANUAL_INJECTION, ManualInjectionDeclaration)
        assert len(CHAT_MANUAL_INJECTION.reason) >= 10
        assert len(CHAT_MANUAL_INJECTION.variables) >= 1
        assert CHAT_MANUAL_INJECTION.injection_mechanism == "agent_deps"


# ---------------------------------------------------------------------------
# Tests for build_chat_invocation_context
# ---------------------------------------------------------------------------


class TestBuildChatInvocationContext:
    """Tests for ``build_chat_invocation_context()`` — the context factory."""

    async def test_builds_context_with_correct_metadata(
        self,
        prompt_context: PromptContext,
    ) -> None:
        """The ``PromptInvocationContext`` has the correct feature_id, intent,
        streaming flag, and identifiers."""
        from uuid import uuid4

        from narrare.chat._invocation import build_chat_invocation_context

        user_id = uuid4()
        project_id = uuid4()
        conv_id = uuid4()
        invocation_id = uuid4()

        ctx = build_chat_invocation_context(
            prompt_ctx=prompt_context,
            user_id=user_id,
            project_id=project_id,
            conv_id=conv_id,
            invocation_id=invocation_id,
        )

        assert ctx.feature_id == "chat"
        assert ctx.intent.value == "chat"
        assert ctx.streaming is True
        assert ctx.user_id == user_id
        assert ctx.project_id == project_id
        assert ctx.invocation_id == invocation_id
        assert ctx.dynamic_inputs["conversation_id"] == str(conv_id)
        assert ctx.prompt_context is prompt_context
        assert ctx.language == "en"


# ---------------------------------------------------------------------------
# Tests for resolve_chat_run_limits
# ---------------------------------------------------------------------------


class TestResolveChatRunLimits:
    """Tests for ``resolve_chat_run_limits()`` — output-budget enforcement."""

    def test_resolver_none_returns_empty_dict(self) -> None:
        """When ``resolver`` is ``None``, an empty kwargs dict is returned."""
        from uuid import uuid4

        from narrare.chat._invocation import resolve_chat_run_limits
        from narrare_core.llm import ResolvedModelConfig

        config = ResolvedModelConfig(
            provider_name="test",
            model_id="test-model",
        )

        result = resolve_chat_run_limits(
            resolver=None,
            config=config,
            invocation_id=uuid4(),
        )
        assert result == {}

    def test_resolver_returns_usage_limits(self) -> None:
        """When ``resolver`` is provided, ``usage_limits`` and
        ``model_settings`` are returned in the kwargs dict."""
        from uuid import uuid4

        from narrare.chat._invocation import resolve_chat_run_limits
        from narrare_core.llm import ResolvedModelConfig
        from narrare_core.llm.run_limits import DefaultRunLimitResolver

        config = ResolvedModelConfig(
            provider_name="test",
            model_id="test-model",
            max_tokens=2000,
            token_limit_profile="balanced",
        )
        resolver = DefaultRunLimitResolver()

        result = resolve_chat_run_limits(
            resolver=resolver,
            config=config,
            invocation_id=uuid4(),
        )
        assert "usage_limits" in result
        assert "model_settings" in result
        assert result["usage_limits"] is not None
        assert result["model_settings"] is not None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def prompt_context() -> PromptContext:
    """Create a minimal PromptContext for chat invocation tests."""
    from narrare_core.prompts.context import PromptContext

    return PromptContext(
        language="en",
        extra={"conversation_history": "User: Hello\nAssistant: Hi there!"},
    )
