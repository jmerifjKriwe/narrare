"""Mode 2 and integration tests for the non-writing invocation adapter (ADR-048).

Migrated from test_non_writing_adapter.py during RULE-04 modularization.

Covers:

- Mode 2 (agent-internal): prepare -> merge -> finalize with manual-injection.
- Evidence correlation (invocation context + prepared propagation).
- Backward compatibility (pipeline=None).
- ComposedInvocation frozen result model.

See: ADR-048, ADR-045 Decision 3/7, CONSTRAINTS.md RULE-03/RULE-10/RULE-11/RULE-22.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import ValidationResult
from narrare_core.ai_invocation.non_writing_adapter import (
    ComposedInvocation,
    compose_invocation,
)
from narrare_core.ai_invocation.pipeline import PreparedInvocation
from narrare_core.llm.intents import LLMIntent
from narrare_core.shared.errors import InvocationValidationError

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
# Mode 2: agent-internal
# ---------------------------------------------------------------------------


class TestMode2AgentInternal:
    """Mode 2: prepare -> merge -> finalize with manual-injection marker."""

    @pytest.mark.asyncio
    async def test_composed_prompt_is_none(self) -> None:
        pipeline = mock_pipeline_pass()

        result = await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            manual_injection=manual_declaration(),
        )
        assert result.composed_prompt is None
        assert result.is_agent_internal
        assert not result.is_composer_driven

    @pytest.mark.asyncio
    async def test_prepare_runs_enrichment_happens(self) -> None:
        pipeline = MagicMock(spec=["prepare", "finalize"])
        prepared_with_enrichment = passing_prepared(
            enriched_inputs={"kb_suggested": "enriched-kb-context"},
        )
        pipeline.prepare = AsyncMock(return_value=prepared_with_enrichment)
        pipeline.finalize = AsyncMock(return_value=passing_finalized())

        result = await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            manual_injection=manual_declaration(),
        )
        pipeline.prepare.assert_called_once()
        # Enrichment available via prepared.context.dynamic_inputs
        assert result.prepared.context.dynamic_inputs.get("kb_suggested") == ("enriched-kb-context")

    @pytest.mark.asyncio
    async def test_finalize_receives_manual_injection_marker(self) -> None:
        """Finalize must NOT receive a placeholder; it receives a typed marker."""
        decl = manual_declaration(
            variables=("entity_summaries", "relationships"),
            injection_mechanism="agent_deps",
        )
        pipeline = mock_pipeline_pass()

        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            manual_injection=decl,
        )
        finalize_args = pipeline.finalize.call_args
        marker = finalize_args.args[0]
        assert isinstance(marker, type(composed_prompt()))
        assert "[manual-injection:agent-internal]" in marker.system
        # Marker encodes declared variables and mechanism (privacy-safe)
        assert "entity_summaries" in marker.user
        assert "relationships" in marker.user
        assert "agent_deps" in marker.user

    @pytest.mark.asyncio
    async def test_merged_context_carries_enrichment_when_prompt_ctx_provided(
        self,
    ) -> None:
        original = prompt_ctx(user_preferences="")
        enriched_inputs = {"user_preferences": "enriched-pref"}
        prepared = passing_prepared(enriched_inputs=enriched_inputs)
        pipeline = mock_pipeline_pass(prepared=prepared)

        result = await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            prompt_context=original,
            manual_injection=manual_declaration(),
        )
        assert result.merged_context is not None
        assert result.merged_context.user_preferences == "enriched-pref"

    @pytest.mark.asyncio
    async def test_merged_context_none_when_no_prompt_ctx(self) -> None:
        pipeline = mock_pipeline_pass()

        result = await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            manual_injection=manual_declaration(),
        )
        assert result.merged_context is None
        assert result.manual_injection is not None

    @pytest.mark.asyncio
    async def test_prepare_validation_failure_still_raises(self) -> None:
        """Mode 2 also gates on prepare validation (no invalid enrichment)."""
        prepared = PreparedInvocation(
            context=invocation_ctx(),
            budget=None,
            validation=ValidationResult(
                status=ValidationStatus.FAIL,
                errors=("invalid context",),
            ),
        )
        pipeline = mock_pipeline_pass(prepared=prepared)

        with pytest.raises(InvocationValidationError, match="Pre-composition"):
            await compose_invocation(
                invocation_pipeline=pipeline,
                invocation_context=invocation_ctx(),
                manual_injection=manual_declaration(),
            )


# ---------------------------------------------------------------------------
# Evidence correlation
# ---------------------------------------------------------------------------


class TestEvidenceCorrelation:
    """Invocation context and prepared state propagate to finalize."""

    @pytest.mark.asyncio
    async def test_prepare_and_finalize_use_same_invocation_context(self) -> None:
        inv_ctx = invocation_ctx(feature_id="kb/consistency")
        pipeline = mock_pipeline_pass()

        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=inv_ctx,
            composer=mock_composer(),
            prompt_context=prompt_ctx(),
            intent=LLMIntent.SUMMARIZE,
        )
        pipeline.prepare.assert_called_once_with(inv_ctx)
        finalize_args = pipeline.finalize.call_args
        assert finalize_args.args[1] is inv_ctx

    @pytest.mark.asyncio
    async def test_finalize_receives_prepared_result(self) -> None:
        prepared = passing_prepared()
        pipeline = mock_pipeline_pass(prepared=prepared)

        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=invocation_ctx(),
            composer=mock_composer(),
            prompt_context=prompt_ctx(),
            intent=LLMIntent.SUMMARIZE,
        )
        finalize_kwargs = pipeline.finalize.call_args.kwargs
        assert finalize_kwargs["prepared"] is prepared


# ---------------------------------------------------------------------------
# Backward compatibility (pipeline=None)
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """pipeline=None falls back to direct composer.build() (Mode 1) or no-op (Mode 2)."""

    @pytest.mark.asyncio
    async def test_pipeline_none_mode1_calls_composer_directly(self) -> None:
        expected = composed_prompt()
        composer = mock_composer(return_value=expected)
        ctx = prompt_ctx()

        result = await compose_invocation(
            invocation_pipeline=None,
            invocation_context=invocation_ctx(),
            composer=composer,
            prompt_context=ctx,
            intent=LLMIntent.SUMMARIZE,
        )
        # Direct composer.build, no merge
        composer.build.assert_called_once_with(LLMIntent.SUMMARIZE, ctx)
        assert result.composed_prompt is expected
        assert result.merged_context is ctx
        # No-op prepared/finalized
        assert result.prepared.validation.is_valid
        assert result.finalized.evidence_recorded is False

    @pytest.mark.asyncio
    async def test_pipeline_none_mode2_returns_minimal_result(self) -> None:
        decl = manual_declaration()

        result = await compose_invocation(
            invocation_pipeline=None,
            invocation_context=invocation_ctx(),
            manual_injection=decl,
        )
        assert result.composed_prompt is None
        assert result.manual_injection is decl
        assert result.prepared.validation.is_valid
        assert result.finalized.evidence_recorded is False


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class TestComposedInvocationModel:
    """ComposedInvocation frozen result model."""

    def test_frozen_result(self) -> None:
        result = ComposedInvocation(
            composed_prompt=None,
            merged_context=None,
            prepared=passing_prepared(),
            finalized=passing_finalized(),
        )
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            result.composed_prompt = composed_prompt()  # type: ignore[misc]

    def test_properties_reflect_mode1(self) -> None:
        result = ComposedInvocation(
            composed_prompt=composed_prompt(),
            merged_context=prompt_ctx(),
            prepared=passing_prepared(),
            finalized=passing_finalized(),
        )
        assert result.is_composer_driven
        assert not result.is_agent_internal

    def test_properties_reflect_mode2(self) -> None:
        result = ComposedInvocation(
            composed_prompt=None,
            merged_context=None,
            prepared=passing_prepared(),
            finalized=passing_finalized(),
            manual_injection=manual_declaration(),
        )
        assert result.is_agent_internal
        assert not result.is_composer_driven
