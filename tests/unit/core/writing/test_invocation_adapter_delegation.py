"""Tests for writing/_invocation_adapter.py — delegation to compose_invocation().

Verifies that ``build_and_validate_prompt()`` delegates the pipeline
orchestration to ``compose_invocation()`` (ADR-048 Q2), wraps
``InvocationValidationError`` as ``WritingError``, and preserves the
``ComposedPrompt`` return type.

See: ADR-048 Q2, CONSTRAINTS.md RULE-03/RULE-10.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import (
    PromptInvocationContext,
    ValidationResult,
)
from narrare_core.ai_invocation.pipeline import FinalizedInvocation, PreparedInvocation
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import InvocationValidationError, WritingError
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


def _passing_prepared() -> PreparedInvocation:
    return PreparedInvocation(
        context=_invocation_ctx(),
        validation=ValidationResult(status=ValidationStatus.PASS),
    )


def _passing_finalized() -> FinalizedInvocation:
    return FinalizedInvocation(
        validation=ValidationResult(status=ValidationStatus.PASS),
    )


def _mock_pipeline_pass() -> MagicMock:
    mock = MagicMock(spec=["prepare", "finalize"])
    mock.prepare = AsyncMock(return_value=_passing_prepared())
    mock.finalize = AsyncMock(return_value=_passing_finalized())
    return mock


# ---------------------------------------------------------------------------
# Delegation verification
# ---------------------------------------------------------------------------


class TestDelegationToComposeInvocation:
    """build_and_validate_prompt delegates to compose_invocation()."""

    @pytest.mark.asyncio
    async def test_delegates_to_compose_invocation(self) -> None:
        """build_and_validate_prompt calls compose_invocation, not inline prepare/finalize."""
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()

        with patch(
            "narrare_core.writing._invocation_adapter.compose_invocation",
            new_callable=AsyncMock,
        ) as mock_compose:
            from narrare_core.ai_invocation.non_writing_adapter import ComposedInvocation

            mock_compose.return_value = ComposedInvocation(
                composed_prompt=_composed_prompt(),
                merged_context=_prompt_ctx(),
                prepared=_passing_prepared(),
                finalized=_passing_finalized(),
                budget=None,
                manual_injection=None,
            )

            result = await build_and_validate_prompt(
                composer=composer,
                invocation_pipeline=mock_pipeline,
                intent=LLMIntent.EXTEND,
                prompt_ctx=_prompt_ctx(),
                invocation_context=_invocation_ctx(),
            )

            # compose_invocation was called with the right arguments
            mock_compose.assert_called_once()
            call_kwargs = mock_compose.call_args.kwargs
            assert call_kwargs["invocation_pipeline"] is mock_pipeline
            assert call_kwargs["composer"] is composer
            assert call_kwargs["intent"] == LLMIntent.EXTEND
            assert call_kwargs["prompt_context"] == _prompt_ctx()

            # The inline pipeline methods were NOT called directly
            mock_pipeline.prepare.assert_not_called()
            mock_pipeline.finalize.assert_not_called()

            assert result == _composed_prompt()

    @pytest.mark.asyncio
    async def test_returns_composed_prompt_type(self) -> None:
        """Return type is ComposedPrompt (not ComposedInvocation)."""
        composer = _mock_composer()
        mock_pipeline = _mock_pipeline_pass()

        result = await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=_invocation_ctx(),
        )

        assert isinstance(result, ComposedPrompt)


# ---------------------------------------------------------------------------
# Error wrapping
# ---------------------------------------------------------------------------


class TestErrorWrapping:
    """InvocationValidationError from compose_invocation is wrapped as WritingError."""

    @pytest.mark.asyncio
    async def test_pre_composition_validation_error_wrapped(self) -> None:
        """Pre-composition InvocationValidationError is wrapped as WritingError."""
        composer = _mock_composer()

        with patch(
            "narrare_core.writing._invocation_adapter.compose_invocation",
            new_callable=AsyncMock,
        ) as mock_compose:
            mock_compose.side_effect = InvocationValidationError(
                "Pre-composition validation failed: missing variable",
                code="INVOCATION_VALIDATION_FAILED",
            )

            with pytest.raises(WritingError, match="Pre-composition validation failed"):
                await build_and_validate_prompt(
                    composer=composer,
                    invocation_pipeline=MagicMock(spec=["prepare", "finalize"]),
                    intent=LLMIntent.EXTEND,
                    prompt_ctx=_prompt_ctx(),
                    invocation_context=_invocation_ctx(),
                )

    @pytest.mark.asyncio
    async def test_final_validation_error_wrapped(self) -> None:
        """Final validation InvocationValidationError is wrapped as WritingError."""
        composer = _mock_composer()

        with patch(
            "narrare_core.writing._invocation_adapter.compose_invocation",
            new_callable=AsyncMock,
        ) as mock_compose:
            mock_compose.side_effect = InvocationValidationError(
                "Final prompt validation failed: prompt too long",
                code="INVOCATION_FINAL_VALIDATION_FAILED",
            )

            with pytest.raises(WritingError, match="Final prompt validation failed"):
                await build_and_validate_prompt(
                    composer=composer,
                    invocation_pipeline=MagicMock(spec=["prepare", "finalize"]),
                    intent=LLMIntent.EXTEND,
                    prompt_ctx=_prompt_ctx(),
                    invocation_context=_invocation_ctx(),
                )

    @pytest.mark.asyncio
    async def test_error_code_preserved(self) -> None:
        """The error code from InvocationValidationError is preserved in WritingError."""
        composer = _mock_composer()

        with patch(
            "narrare_core.writing._invocation_adapter.compose_invocation",
            new_callable=AsyncMock,
        ) as mock_compose:
            mock_compose.side_effect = InvocationValidationError(
                "Validation failed",
                code="CUSTOM_CODE",
            )

            with pytest.raises(WritingError) as exc_info:
                await build_and_validate_prompt(
                    composer=composer,
                    invocation_pipeline=MagicMock(spec=["prepare", "finalize"]),
                    intent=LLMIntent.EXTEND,
                    prompt_ctx=_prompt_ctx(),
                    invocation_context=_invocation_ctx(),
                )

            assert exc_info.value.code == "CUSTOM_CODE"

    @pytest.mark.asyncio
    async def test_error_without_code_gets_default(self) -> None:
        """When InvocationValidationError has no code, default is used."""
        composer = _mock_composer()

        with patch(
            "narrare_core.writing._invocation_adapter.compose_invocation",
            new_callable=AsyncMock,
        ) as mock_compose:
            mock_compose.side_effect = InvocationValidationError("Validation failed")

            with pytest.raises(WritingError) as exc_info:
                await build_and_validate_prompt(
                    composer=composer,
                    invocation_pipeline=MagicMock(spec=["prepare", "finalize"]),
                    intent=LLMIntent.EXTEND,
                    prompt_ctx=_prompt_ctx(),
                    invocation_context=_invocation_ctx(),
                )

            assert exc_info.value.code == "INVOCATION_VALIDATION_FAILED"

    @pytest.mark.asyncio
    async def test_original_exception_chained(self) -> None:
        """The original InvocationValidationError is chained as __cause__."""
        composer = _mock_composer()

        original = InvocationValidationError("Validation failed", code="TEST")

        with patch(
            "narrare_core.writing._invocation_adapter.compose_invocation",
            new_callable=AsyncMock,
        ) as mock_compose:
            mock_compose.side_effect = original

            with pytest.raises(WritingError) as exc_info:
                await build_and_validate_prompt(
                    composer=composer,
                    invocation_pipeline=MagicMock(spec=["prepare", "finalize"]),
                    intent=LLMIntent.EXTEND,
                    prompt_ctx=_prompt_ctx(),
                    invocation_context=_invocation_ctx(),
                )

            assert exc_info.value.__cause__ is original


# ---------------------------------------------------------------------------
# Pipeline=None fallback (delegated to compose_invocation)
# ---------------------------------------------------------------------------


class TestPipelineNoneFallback:
    """pipeline=None fallback is delegated to compose_invocation()."""

    @pytest.mark.asyncio
    async def test_no_pipeline_delegates_to_compose_invocation(self) -> None:
        """When pipeline is None, compose_invocation handles the fallback."""
        composer = _mock_composer()

        with patch(
            "narrare_core.writing._invocation_adapter.compose_invocation",
            new_callable=AsyncMock,
        ) as mock_compose:
            from narrare_core.ai_invocation.non_writing_adapter import ComposedInvocation

            mock_compose.return_value = ComposedInvocation(
                composed_prompt=_composed_prompt(),
                merged_context=_prompt_ctx(),
                prepared=_passing_prepared(),
                finalized=_passing_finalized(),
                budget=None,
                manual_injection=None,
            )

            result = await build_and_validate_prompt(
                composer=composer,
                invocation_pipeline=None,
                intent=LLMIntent.EXTEND,
                prompt_ctx=_prompt_ctx(),
            )

            # compose_invocation was called with pipeline=None
            mock_compose.assert_called_once()
            assert mock_compose.call_args.kwargs["invocation_pipeline"] is None
            assert result == _composed_prompt()

    @pytest.mark.asyncio
    async def test_no_pipeline_returns_composer_result(self) -> None:
        """When pipeline is None, the composer result is returned."""
        expected = ComposedPrompt(system="custom sys", user="custom usr")
        composer = _mock_composer(return_value=expected)

        result = await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=None,
            intent=LLMIntent.WRITE,
            prompt_ctx=_prompt_ctx(),
        )

        assert result is expected
