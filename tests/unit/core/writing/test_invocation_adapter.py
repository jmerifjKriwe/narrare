"""Tests for writing/_invocation_adapter.py — InvocationPipeline integration.

Covers:
1. No pipeline → falls back to composer.build() directly.
2. Pipeline + context → runs prepare → build → finalize, returns prompt.
3. Variable validation fails → raises WritingError.
4. Final validation fails → raises WritingError.
5. Both validations pass → returns ComposedPrompt.
6. Evidence recording → verify pipeline.finalize is called.
7. Enricher modifies context → composer receives original prompt_ctx.
8. Call order integration: prepare → build → finalize.

Auto-context creation tests are in test_invocation_auto_context.py.

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
from narrare_core.shared.errors import WritingError
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


def _failing_result(errors: tuple[str, ...]) -> ValidationResult:
    return ValidationResult(status=ValidationStatus.FAIL, errors=errors)


def _mock_pipeline_pass() -> MagicMock:
    """Create a mock InvocationPipeline with passing validations."""
    mock = MagicMock(spec=["prepare", "finalize"])
    mock.prepare = AsyncMock(return_value=_passing_prepared())
    mock.finalize = AsyncMock(return_value=_passing_finalized())
    return mock


# ---------------------------------------------------------------------------
# Fallback when pipeline or context is missing
# ---------------------------------------------------------------------------


class TestFallbackWithoutPipeline:
    """When no invocation_pipeline is provided, falls back to composer.build()."""

    @pytest.mark.asyncio
    async def test_no_pipeline_calls_composer_directly(self) -> None:
        composer = _mock_composer()
        result = await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=None,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
        )
        composer.build.assert_called_once_with(LLMIntent.EXTEND, _prompt_ctx())
        assert result == _composed_prompt()

    @pytest.mark.asyncio
    async def test_no_pipeline_returns_composer_result(self) -> None:
        expected = ComposedPrompt(system="custom sys", user="custom usr")
        composer = _mock_composer(return_value=expected)
        result = await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=None,
            intent=LLMIntent.WRITE,
            prompt_ctx=_prompt_ctx(),
        )
        assert result is expected


# ---------------------------------------------------------------------------
# Full pipeline with passing validations
# ---------------------------------------------------------------------------


class TestSuccessfulPipeline:
    """When both pipeline and context are provided, runs full pipeline."""

    @pytest.mark.asyncio
    async def test_runs_prepare_build_finalize(self) -> None:
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()

        result = await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=_invocation_ctx(),
        )
        mock_pipeline.prepare.assert_called_once_with(_invocation_ctx())
        composer.build.assert_called_once_with(LLMIntent.EXTEND, _prompt_ctx())
        mock_pipeline.finalize.assert_called_once()
        assert result == _composed_prompt()

    @pytest.mark.asyncio
    async def test_both_validations_pass_returns_prompt(self) -> None:
        expected = _composed_prompt()
        composer = _mock_composer(return_value=expected)
        mock_pipeline = _mock_pipeline_pass()

        result = await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=_invocation_ctx(),
        )
        assert result is expected


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------


class TestVariableValidationFailure:
    """Pre-composition validation failure blocks invocation."""

    @pytest.mark.asyncio
    async def test_raises_writing_error(self) -> None:
        composer = _mock_composer()
        mock_pipeline = MagicMock(spec=["prepare", "finalize"])
        mock_pipeline.prepare = AsyncMock(
            return_value=MagicMock(
                spec=["validation"],
                validation=_failing_result(("missing variable: tone_instructions",)),
            )
        )

        with pytest.raises(WritingError, match="Pre-composition validation failed"):
            await build_and_validate_prompt(
                composer=composer,
                invocation_pipeline=mock_pipeline,
                intent=LLMIntent.EXTEND,
                prompt_ctx=_prompt_ctx(),
                invocation_context=_invocation_ctx(),
            )
        composer.build.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_includes_variable_errors(self) -> None:
        composer = _mock_composer()
        mock_pipeline = MagicMock(spec=["prepare", "finalize"])
        mock_pipeline.prepare = AsyncMock(
            return_value=MagicMock(
                spec=["validation"],
                validation=_failing_result(("missing: kb_characters", "missing: writing_language")),
            )
        )

        with pytest.raises(
            WritingError, match=r"missing: kb_characters.*missing: writing_language"
        ):
            await build_and_validate_prompt(
                composer=composer,
                invocation_pipeline=mock_pipeline,
                intent=LLMIntent.EXTEND,
                prompt_ctx=_prompt_ctx(),
                invocation_context=_invocation_ctx(),
            )


class TestFinalValidationFailure:
    """Final prompt validation failure blocks invocation."""

    @pytest.mark.asyncio
    async def test_raises_writing_error(self) -> None:
        composer = _mock_composer()
        mock_pipeline = MagicMock(spec=["prepare", "finalize"])
        mock_pipeline.prepare = AsyncMock(return_value=_passing_prepared())
        mock_pipeline.finalize = AsyncMock(
            return_value=MagicMock(
                spec=["validation"],
                validation=_failing_result(("unsafe user-content boundary",)),
            )
        )

        with pytest.raises(WritingError, match="Final prompt validation failed"):
            await build_and_validate_prompt(
                composer=composer,
                invocation_pipeline=mock_pipeline,
                intent=LLMIntent.EXTEND,
                prompt_ctx=_prompt_ctx(),
                invocation_context=_invocation_ctx(),
            )

    @pytest.mark.asyncio
    async def test_composer_was_called_before_final_failure(self) -> None:
        composer = _mock_composer()
        mock_pipeline = MagicMock(spec=["prepare", "finalize"])
        mock_pipeline.prepare = AsyncMock(return_value=_passing_prepared())
        mock_pipeline.finalize = AsyncMock(
            return_value=MagicMock(
                spec=["validation"],
                validation=_failing_result(("prompt too long",)),
            )
        )

        with pytest.raises(WritingError):
            await build_and_validate_prompt(
                composer=composer,
                invocation_pipeline=mock_pipeline,
                intent=LLMIntent.EXTEND,
                prompt_ctx=_prompt_ctx(),
                invocation_context=_invocation_ctx(),
            )
        # Composer was called (prepare passed), but finalize rejected
        composer.build.assert_called_once()


# ---------------------------------------------------------------------------
# Evidence recording
# ---------------------------------------------------------------------------


class TestEvidenceRecording:
    """Verify finalize is called with correct arguments for evidence."""

    @pytest.mark.asyncio
    async def test_finalize_receives_prepared_result(self) -> None:
        composer = _mock_composer()
        prepared = _passing_prepared()
        finalized = _passing_finalized()
        mock_pipeline = MagicMock(spec=["prepare", "finalize"])
        mock_pipeline.prepare = AsyncMock(return_value=prepared)
        mock_pipeline.finalize = AsyncMock(return_value=finalized)

        inv_ctx = _invocation_ctx()
        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=inv_ctx,
        )

        call_args = mock_pipeline.finalize.call_args
        assert call_args.args[0] == _composed_prompt()
        assert call_args.args[1] is inv_ctx
        assert call_args.kwargs["prepared"] is prepared


# ---------------------------------------------------------------------------
# Composer receives original context
# ---------------------------------------------------------------------------


class TestComposerReceivesOriginalContext:
    """Enriched context must NOT override the prompt_ctx passed to composer."""

    @pytest.mark.asyncio
    async def test_enricher_does_not_affect_composer_input(self) -> None:
        original_ctx = _prompt_ctx()
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=original_ctx,
            invocation_context=_invocation_ctx(),
        )
        composer.build.assert_called_once_with(LLMIntent.EXTEND, original_ctx)


# ---------------------------------------------------------------------------
# Call order
# ---------------------------------------------------------------------------


class TestCallOrder:
    """Integration: verify prepare → build → finalize execution order."""

    @pytest.mark.asyncio
    async def test_calls_happen_in_correct_order(self) -> None:
        call_order: list[str] = []
        composer = MagicMock(spec=["build"])
        composer.build = AsyncMock(
            side_effect=lambda intent, ctx: (
                call_order.append("build"),
                _composed_prompt(),
            )[1],
        )
        mock_pipeline = MagicMock(spec=["prepare", "finalize"])
        mock_pipeline.prepare = AsyncMock(
            side_effect=lambda ctx: (
                call_order.append("prepare"),
                _passing_prepared(),
            )[1],
        )
        mock_pipeline.finalize = AsyncMock(
            side_effect=lambda *a, **kw: (
                call_order.append("finalize"),
                _passing_finalized(),
            )[1],
        )

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=_invocation_ctx(),
        )
        assert call_order == ["prepare", "build", "finalize"]
