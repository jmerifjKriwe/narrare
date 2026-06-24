"""Tests for ADR-045 Decision 3 prompt-context merge in _invocation_adapter.py.

Split from ``test_invocation_adapter.py`` to respect RULE-04.

Verifies that ``build_and_validate_prompt()`` Phase 2 composes the prompt
from the *merged* context (enricher dynamic_inputs flow in), while
caller-provided fields keep higher RULE-22 precedence than enricher
suggestions.

See: ADR-045 Decision 3, CONSTRAINTS.md RULE-04/RULE-22.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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


def _passing_finalized() -> FinalizedInvocation:
    return FinalizedInvocation(
        validation=ValidationResult(status=ValidationStatus.PASS),
    )


class TestComposerReceivesMergedContext:
    """Prepared dynamic_inputs flow into the composer's context (ADR-045 D3).

    Empty caller fields are filled by enricher dynamic_inputs; non-empty
    caller fields are preserved because caller-provided values have higher
    RULE-22 precedence than generated suggestions.
    """

    @pytest.mark.asyncio
    async def test_enriched_dynamic_inputs_reach_composer_context(self) -> None:
        """Prepared user_preferences fills the empty composer context field."""
        composer = _mock_composer()
        prepared = PreparedInvocation(
            context=_invocation_ctx().model_copy(
                update={"dynamic_inputs": {"user_preferences": "Avoid adverbs."}}
            ),
            validation=ValidationResult(status=ValidationStatus.PASS),
        )
        mock_pipeline = MagicMock(spec=["prepare", "finalize"])
        mock_pipeline.prepare = AsyncMock(return_value=prepared)
        mock_pipeline.finalize = AsyncMock(return_value=_passing_finalized())

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=_prompt_ctx(),
            invocation_context=_invocation_ctx(),
        )

        _, merged_ctx = composer.build.call_args.args
        assert merged_ctx.user_preferences == "Avoid adverbs."

    @pytest.mark.asyncio
    async def test_caller_field_takes_precedence_over_enricher(self) -> None:
        """A non-empty caller field wins over the enricher suggestion (RULE-22)."""
        composer = _mock_composer()
        prepared = PreparedInvocation(
            context=_invocation_ctx().model_copy(
                update={
                    "dynamic_inputs": {
                        "user_preferences": "enricher-suggested preference",
                    }
                }
            ),
            validation=ValidationResult(status=ValidationStatus.PASS),
        )
        mock_pipeline = MagicMock(spec=["prepare", "finalize"])
        mock_pipeline.prepare = AsyncMock(return_value=prepared)
        mock_pipeline.finalize = AsyncMock(return_value=_passing_finalized())
        caller_ctx = PromptContext(
            language="en",
            project_title="Test Novel",
            genre="fantasy",
            mode="extend_chapter",
            user_preferences="caller-explicit preference",
        )

        await build_and_validate_prompt(
            composer=composer,
            invocation_pipeline=mock_pipeline,
            intent=LLMIntent.EXTEND,
            prompt_ctx=caller_ctx,
            invocation_context=_invocation_ctx(),
        )

        _, merged_ctx = composer.build.call_args.args
        assert merged_ctx.user_preferences == "caller-explicit preference"
