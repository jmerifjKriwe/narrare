"""Tests for the non-writing invocation adapter (ADR-048).

Covers both composition modes:

- Mode 1 (composer-driven): prepare -> merge -> compose -> finalize.
- Mode 2 (agent-internal): prepare -> merge -> finalize with manual-injection marker.

Plus error cases, enrichment propagation, evidence correlation, budget,
backward-compat (pipeline=None), and RULE-22 precedence preservation.

See: ADR-048, ADR-045 Decision 3/7, CONSTRAINTS.md RULE-03/RULE-10/RULE-11/RULE-22.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import ValidationResult
from narrare_core.ai_invocation.non_writing_adapter import compose_invocation
from narrare_core.ai_invocation.pipeline import FinalizedInvocation, PreparedInvocation
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.shared.errors import InvocationValidationError

if TYPE_CHECKING:
    from narrare_core.prompts.context import PromptContext

from ._non_writing_fakes import (
    composed_prompt,
    invocation_ctx,
    manual_declaration,
    mock_composer,
    mock_pipeline_pass,
    passing_finalized,
    passing_prepared,
    prompt_ctx,
)

# ---------------------------------------------------------------------------
# Mode resolution errors
# ---------------------------------------------------------------------------


class TestModeResolutionErrors:
    """Mutual exclusivity of composer and manual_injection."""

    @pytest.mark.asyncio
    async def test_both_composer_and_manual_injection_raises(self) -> None:
        with pytest.raises(ValueError, match="not both"):
            await compose_invocation(
                invocation_pipeline=mock_pipeline_pass(),
                invocation_context=invocation_ctx(),
                composer=mock_composer(),
                prompt_context=prompt_ctx(),
                intent=LLMIntent.SUMMARIZE,
                manual_injection=manual_declaration(),
            )

    @pytest.mark.asyncio
    async def test_neither_composer_nor_manual_injection_raises(self) -> None:
        with pytest.raises(ValueError, match="either"):
            await compose_invocation(
                invocation_pipeline=mock_pipeline_pass(),
                invocation_context=invocation_ctx(),
            )

    @pytest.mark.asyncio
    async def test_mode1_without_intent_raises(self) -> None:
        with pytest.raises(ValueError, match="intent"):
            await compose_invocation(
                invocation_pipeline=mock_pipeline_pass(),
                invocation_context=invocation_ctx(),
                composer=mock_composer(),
                prompt_context=prompt_ctx(),
            )

    @pytest.mark.asyncio
    async def test_mode1_without_prompt_context_raises(self) -> None:
        with pytest.raises(ValueError, match="prompt_context"):
            await compose_invocation(
                invocation_pipeline=mock_pipeline_pass(),
                invocation_context=invocation_ctx(),
                composer=mock_composer(),
                intent=LLMIntent.SUMMARIZE,
            )


# ---------------------------------------------------------------------------
# Mode 1: composer-driven
# ---------------------------------------------------------------------------


class TestMode1ComposerDriven:
    """Mode 1: prepare -> merge -> compose -> finalize with real prompt."""

    @pytest.mark.asyncio
    async def test_returns_composed_prompt(self) -> None:
        expected = composed_prompt()
        composer = mock_composer(return_value=expected)
        pipeline = mock_pipeline_pass()

        result = await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            composer=composer,
            prompt_context=prompt_ctx(),
            intent=LLMIntent.SUMMARIZE,
        )
        assert result.composed_prompt is expected
        assert result.is_composer_driven
        assert not result.is_agent_internal

    @pytest.mark.asyncio
    async def test_runs_prepare_then_compose_then_finalize(self) -> None:
        call_order: list[str] = []
        composer = MagicMock(spec=["build"])
        composer.build = AsyncMock(
            side_effect=lambda intent, ctx: (
                call_order.append("compose"),
                composed_prompt(),
            )[1],
        )
        pipeline = MagicMock(spec=["prepare", "finalize"])
        pipeline.prepare = AsyncMock(
            side_effect=lambda ctx: (
                call_order.append("prepare"),
                passing_prepared(),
            )[1],
        )
        pipeline.finalize = AsyncMock(
            side_effect=lambda *a, **kw: (
                call_order.append("finalize"),
                passing_finalized(),
            )[1],
        )

        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            composer=composer,
            prompt_context=prompt_ctx(),
            intent=LLMIntent.SUMMARIZE,
        )
        assert call_order == ["prepare", "compose", "finalize"]

    @pytest.mark.asyncio
    async def test_composer_receives_merged_context_not_original(self) -> None:
        """ADR-045 Decision 3: compose with MERGED context, not original."""
        original = prompt_ctx(user_preferences="")
        enriched_inputs = {"user_preferences": "enriched-pref-text"}
        prepared = passing_prepared(enriched_inputs=enriched_inputs)
        composer = mock_composer()
        pipeline = mock_pipeline_pass(prepared=prepared)

        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            composer=composer,
            prompt_context=original,
            intent=LLMIntent.SUMMARIZE,
        )

        composer.build.assert_called_once()
        passed_ctx = composer.build.call_args.args[1]
        # Enrichment merged into the context the composer received
        assert passed_ctx.user_preferences == "enriched-pref-text"

    @pytest.mark.asyncio
    async def test_enrichment_reaches_composed_prompt(self) -> None:
        original = prompt_ctx(user_preferences="")
        enriched_inputs = {"user_preferences": "enriched-pref-text"}
        prepared = passing_prepared(enriched_inputs=enriched_inputs)

        captured: list[PromptContext] = []
        composer = MagicMock(spec=["build"])
        composer.build = AsyncMock(
            side_effect=lambda intent, ctx: (
                captured.append(ctx),
                composed_prompt(),
            )[1],
        )
        pipeline = mock_pipeline_pass(prepared=prepared)

        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            composer=composer,
            prompt_context=original,
            intent=LLMIntent.SUMMARIZE,
        )
        assert len(captured) == 1
        assert captured[0].user_preferences == "enriched-pref-text"

    @pytest.mark.asyncio
    async def test_higher_precedence_existing_values_preserved(self) -> None:
        """RULE-22: caller-provided values must not be overwritten by enricher."""
        original = prompt_ctx(author_instructions="Use explicit instruction.")
        enriched_inputs = {"author_instructions": "enricher lower precedence."}
        prepared = passing_prepared(enriched_inputs=enriched_inputs)
        composer = mock_composer()
        pipeline = mock_pipeline_pass(prepared=prepared)

        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            composer=composer,
            prompt_context=original,
            intent=LLMIntent.SUMMARIZE,
        )
        passed_ctx = composer.build.call_args.args[1]
        assert passed_ctx.author_instructions == "Use explicit instruction."

    @pytest.mark.asyncio
    async def test_finalize_receives_real_composed_prompt(self) -> None:
        """Evidence fingerprint must match the real prompt, not a placeholder."""
        real_prompt = ComposedPrompt(system="unique sys", user="unique usr")
        composer = mock_composer(return_value=real_prompt)
        pipeline = mock_pipeline_pass()

        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            composer=composer,
            prompt_context=prompt_ctx(),
            intent=LLMIntent.SUMMARIZE,
        )
        finalize_args = pipeline.finalize.call_args
        assert finalize_args.args[0] is real_prompt

    @pytest.mark.asyncio
    async def test_prepare_validation_failure_raises_invocation_error(self) -> None:
        prepared = PreparedInvocation(
            context=invocation_ctx(),
            budget=None,
            validation=ValidationResult(
                status=ValidationStatus.FAIL,
                errors=("missing variable: tone",),
            ),
        )
        pipeline = mock_pipeline_pass(prepared=prepared)
        composer = mock_composer()

        with pytest.raises(InvocationValidationError, match="Pre-composition"):
            await compose_invocation(
                invocation_pipeline=pipeline,
                invocation_context=invocation_ctx(),
                composer=composer,
                prompt_context=prompt_ctx(),
                intent=LLMIntent.SUMMARIZE,
            )
        composer.build.assert_not_called()

    @pytest.mark.asyncio
    async def test_final_validation_failure_raises_invocation_error(self) -> None:
        finalized = FinalizedInvocation(
            validation=ValidationResult(
                status=ValidationStatus.FAIL,
                errors=("prompt too long",),
            ),
            evidence_recorded=False,
        )
        pipeline = mock_pipeline_pass(finalized=finalized)
        composer = mock_composer()

        with pytest.raises(InvocationValidationError, match="Final prompt"):
            await compose_invocation(
                invocation_pipeline=pipeline,
                invocation_context=invocation_ctx(),
                composer=composer,
                prompt_context=prompt_ctx(),
                intent=LLMIntent.SUMMARIZE,
            )


# ---------------------------------------------------------------------------
# Budget propagation
# ---------------------------------------------------------------------------


class TestBudgetPropagation:
    """OutputBudgetDecision from prepare() reaches the result."""

    @pytest.mark.asyncio
    async def test_mode1_budget_in_result(self) -> None:
        from narrare_core.ai_invocation.budgets._types import (
            OutputBudget,
            OutputBudgetDecision,
        )

        budget = OutputBudgetDecision(
            budget=OutputBudget(max_tokens=4096, profile="balanced"),
            source="intent_profile",
            reason="Test",
        )
        prepared = passing_prepared(budget=budget)
        pipeline = mock_pipeline_pass(prepared=prepared)

        result = await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            composer=mock_composer(),
            prompt_context=prompt_ctx(),
            intent=LLMIntent.SUMMARIZE,
        )
        assert result.budget is budget
        assert result.budget is not None
        assert result.budget.budget.profile == "balanced"

    @pytest.mark.asyncio
    async def test_mode2_budget_in_result(self) -> None:
        from narrare_core.ai_invocation.budgets._types import (
            OutputBudget,
            OutputBudgetDecision,
        )

        budget = OutputBudgetDecision(
            budget=OutputBudget(max_tokens=8192, profile="long_texts"),
            source="intent_profile",
            reason="Test",
        )
        prepared = passing_prepared(budget=budget)
        pipeline = mock_pipeline_pass(prepared=prepared)

        result = await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            manual_injection=manual_declaration(),
        )
        assert result.budget is budget
