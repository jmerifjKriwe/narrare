"""Tests for invocation call-order integration in _invocation_adapter.py.

Covers:
- Integration: verify prepare → build → finalize execution order.

Extracted from test_invocation_adapter.py to respect RULE-04 file-size limits.

See:
    INFRA-013, ADR-038, ADR-045, CONSTRAINTS.md RULE-10/RULE-11.
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


def _passing_prepared(context: PromptInvocationContext | None = None) -> PreparedInvocation:
    return PreparedInvocation(
        context=context or _invocation_ctx(),
        validation=ValidationResult(status=ValidationStatus.PASS),
    )


def _passing_finalized() -> FinalizedInvocation:
    return FinalizedInvocation(
        validation=ValidationResult(status=ValidationStatus.PASS),
    )


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
                _passing_prepared(ctx),
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
