"""Tests for auto-context creation in _invocation_adapter.py.

When the invocation pipeline is wired but no explicit invocation_context
is provided, the adapter auto-creates a minimal PromptInvocationContext
from the available intent and prompt_ctx data.

Covers:
1. Pipeline runs (prepare + finalize) when context is auto-created.
2. Auto-created context has correct feature_id and intent.
3. Auto-created context inherits language/mode from prompt_ctx.
4. Auto-created context has streaming=True.
5. Auto-created context has user_id=None, project_id=None.
6. Explicit context is preferred over auto-creation.

See:
    INFRA-013, ADR-038, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import (
    PromptInvocationContext,
    ValidationResult,
)
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.prompts.context import PromptContext
from narrare_core.writing._invocation_adapter import build_and_validate_prompt


def _prompt_ctx() -> PromptContext:
    return PromptContext(
        language="en", project_title="Test Novel", genre="fantasy", mode="extend_chapter"
    )


def _invocation_ctx() -> PromptInvocationContext:
    return PromptInvocationContext(feature_id="test-feature", intent=LLMIntent.EXTEND)


def _composed_prompt() -> ComposedPrompt:
    return ComposedPrompt(system="system prompt", user="user prompt")


def _mock_composer(return_value: ComposedPrompt | None = None) -> MagicMock:
    composer = MagicMock(spec=["build"])
    composer.build = AsyncMock(return_value=return_value or _composed_prompt())
    return composer


def _passing_prepared() -> MagicMock:
    m = MagicMock(spec=["validation"])
    m.validation = ValidationResult(status=ValidationStatus.PASS)
    return m


def _passing_finalized() -> MagicMock:
    m = MagicMock(spec=["validation"])
    m.validation = ValidationResult(status=ValidationStatus.PASS)
    return m


def _mock_pipeline_pass() -> MagicMock:
    """Create a mock InvocationPipeline with passing validations."""
    mock = MagicMock(spec=["prepare", "finalize"])
    mock.prepare = AsyncMock(return_value=_passing_prepared())
    mock.finalize = AsyncMock(return_value=_passing_finalized())
    return mock


# ---------------------------------------------------------------------------
# Auto-context creation
# ---------------------------------------------------------------------------


class TestAutoContextCreation:
    """When pipeline exists but invocation_context is None, auto-creates context."""

    @pytest.mark.asyncio
    async def test_pipeline_with_no_context_auto_creates_and_runs(self) -> None:
        """Pipeline runs (prepare + finalize) when context is auto-created."""
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=None,
        )
        # Pipeline should run — prepare and finalize called, not skipped
        mock_pipeline.prepare.assert_called_once()
        mock_pipeline.finalize.assert_called_once()
        composer.build.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_created_context_has_correct_feature_id(self) -> None:
        """Auto-created context uses 'writing_{intent.value}' as feature_id."""
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=None,
        )

        # Inspect the context passed to prepare
        prepared_ctx = mock_pipeline.prepare.call_args.args[0]
        assert prepared_ctx.feature_id == "writing_extend"
        assert prepared_ctx.intent == LLMIntent.EXTEND

    @pytest.mark.asyncio
    async def test_auto_created_context_has_correct_language(self) -> None:
        """Auto-created context inherits language from prompt_ctx."""
        composer = _mock_composer()
        prompt_ctx = PromptContext(
            language="de", writing_language="Schweizerdeutsch", mode="rewrite"
        )
        mock_pipeline = _mock_pipeline_pass()

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.REWRITE,
            prompt_ctx=prompt_ctx,
            invocation_context=None,
        )

        prepared_ctx = mock_pipeline.prepare.call_args.args[0]
        assert prepared_ctx.language == "de"
        assert prepared_ctx.output_language == "Schweizerdeutsch"
        assert prepared_ctx.mode == "rewrite"

    @pytest.mark.asyncio
    async def test_auto_created_context_streaming_true(self) -> None:
        """Auto-created context has streaming=True."""
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.WRITE,
            prompt_ctx=_prompt_ctx(),
            invocation_context=None,
        )

        prepared_ctx = mock_pipeline.prepare.call_args.args[0]
        assert prepared_ctx.streaming is True

    @pytest.mark.asyncio
    async def test_auto_created_context_has_no_user_or_project(self) -> None:
        """Auto-created context has user_id=None and project_id=None.

        The adapter layer does not have access to authenticated user context.
        Enrichers that need these values must handle None gracefully.
        """
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.WRITE,
            prompt_ctx=_prompt_ctx(),
            invocation_context=None,
        )

        prepared_ctx = mock_pipeline.prepare.call_args.args[0]
        assert prepared_ctx.user_id is None
        assert prepared_ctx.project_id is None

    @pytest.mark.asyncio
    async def test_explicit_context_preferred_over_auto(self) -> None:
        """When explicit invocation_context is provided, it is used as-is."""
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()
        explicit_ctx = _invocation_ctx()

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=explicit_ctx,
        )

        prepared_ctx = mock_pipeline.prepare.call_args.args[0]
        assert prepared_ctx is explicit_ctx
        assert prepared_ctx.feature_id == "test-feature"  # not auto-generated
