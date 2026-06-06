"""Tests for InvocationPipeline.prepare() — pre-composition phase.

10 mandatory test cases:
 1. Happy path — validator passes, enricher adds data, resolver returns budget.
 2. No components — all None, returns PASS with no enrichment/budget.
 3. Variable validation fails — early return, no enrichment, no budget.
 4. Multiple enrichers in sequence — each receives previous output.
 5. Enricher modifies dynamic_inputs — tracked in enrichment_result.
 6. Enricher is a no-op — enrichment_result reflects no change.
 7. Budget resolver missing — budget is None in result.
 8. Validator missing — skips validation, defaults to PASS.
 9. Context immutability — original context not mutated.
10. Protocol conformance — InvocationPipeline has prepare and finalize.

See: ADR-038, INFRA-013, CONSTRAINTS.md RULE-04/RULE-10.
"""

from __future__ import annotations

import pytest

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import (
    ValidationResult,
)
from narrare_core.ai_invocation.pipeline import (
    InvocationPipeline,
    PreparedInvocation,
)

from .conftest import (
    FakeBudgetResolver,
    FakeContextEnricher,
    FakeVariableValidator,
    NoopEnricher,
    make_invocation_context,
)

# 1. Happy path


class TestPrepareHappyPath:
    """1. Happy path — validator passes, enricher adds data, resolver returns budget."""

    @pytest.mark.asyncio
    async def test_returns_prepared_invocation_with_all_results(self) -> None:
        validator = FakeVariableValidator()
        enricher = FakeContextEnricher("user_preferences", "some prefs")
        resolver = FakeBudgetResolver()

        pipeline = InvocationPipeline(
            enrichers=[enricher],
            variable_validator=validator,
            budget_resolver=resolver,
        )
        ctx = make_invocation_context()
        result = await pipeline.prepare(ctx)

        assert isinstance(result, PreparedInvocation)
        assert result.validation.is_valid
        assert result.budget is not None
        assert result.budget.budget.max_tokens == 4096
        assert result.enrichment_result is not None
        assert "user_preferences" in result.enrichment_result.enriched_fields
        assert result.context.dynamic_inputs["user_preferences"] == "some prefs"


# 2. No components


class TestPrepareNoComponents:
    """2. No components — all None, returns PASS with no enrichment/budget."""

    @pytest.mark.asyncio
    async def test_returns_pass_with_no_enrichment_or_budget(self) -> None:
        pipeline = InvocationPipeline()
        ctx = make_invocation_context()
        result = await pipeline.prepare(ctx)

        assert result.validation.status == ValidationStatus.PASS
        assert result.validation.errors == ()
        assert result.budget is None
        assert result.enrichment_result is None
        assert result.context == ctx


# 3. Validation fails


class TestPrepareValidationFails:
    """3. Variable validation fails — early return, no enrichment, no budget."""

    @pytest.mark.asyncio
    async def test_returns_early_on_validation_failure(self) -> None:
        fail_result = ValidationResult(
            status=ValidationStatus.FAIL,
            errors=("Missing required variable",),
        )
        validator = FakeVariableValidator(result=fail_result)
        enricher = FakeContextEnricher("key", "value")
        resolver = FakeBudgetResolver()

        pipeline = InvocationPipeline(
            enrichers=[enricher],
            variable_validator=validator,
            budget_resolver=resolver,
        )
        ctx = make_invocation_context()
        result = await pipeline.prepare(ctx)

        assert not result.validation.is_valid
        assert result.budget is None
        assert result.enrichment_result is None
        assert enricher.call_count == 0


# 4. Multiple enrichers


class TestPrepareMultipleEnrichers:
    """4. Multiple enrichers in sequence — each receives previous output."""

    @pytest.mark.asyncio
    async def test_each_enricher_receives_previous_output(self) -> None:
        enricher_a = FakeContextEnricher("step_a", "A")
        enricher_b = FakeContextEnricher("step_b", "B")

        pipeline = InvocationPipeline(enrichers=[enricher_a, enricher_b])
        ctx = make_invocation_context()
        result = await pipeline.prepare(ctx)

        assert result.context.dynamic_inputs["step_a"] == "A"
        assert result.context.dynamic_inputs["step_b"] == "B"
        assert enricher_a.call_count == 1
        assert enricher_b.call_count == 1


# 5. Enricher tracks fields


class TestPrepareEnricherTracksFields:
    """5. Enricher modifies dynamic_inputs — tracked in enrichment_result."""

    @pytest.mark.asyncio
    async def test_enriched_fields_tracked(self) -> None:
        enricher = FakeContextEnricher("kb_suggested", "some kb data")

        pipeline = InvocationPipeline(enrichers=[enricher])
        ctx = make_invocation_context()
        result = await pipeline.prepare(ctx)

        assert result.enrichment_result is not None
        assert "kb_suggested" in result.enrichment_result.enriched_fields
        assert len(result.enrichment_result.enrichment_sources) == 1
        assert result.enrichment_result.enrichment_sources[0] == ("enricher_0", "ran")


# 6. Noop enricher


class TestPrepareEnricherNoop:
    """6. Enricher is a no-op — enrichment_result reflects no change."""

    @pytest.mark.asyncio
    async def test_noop_enricher_produces_no_enriched_fields(self) -> None:
        noop = NoopEnricher()

        pipeline = InvocationPipeline(enrichers=[noop])
        ctx = make_invocation_context()
        result = await pipeline.prepare(ctx)

        assert result.enrichment_result is not None
        assert len(result.enrichment_result.enriched_fields) == 0
        assert len(result.enrichment_result.enrichment_sources) == 0
        assert noop.call_count == 1


# 7. No budget resolver


class TestPrepareBudgetResolverMissing:
    """7. Budget resolver missing — budget is None in result."""

    @pytest.mark.asyncio
    async def test_budget_none_when_no_resolver(self) -> None:
        pipeline = InvocationPipeline(enrichers=[FakeContextEnricher("k", "v")])
        ctx = make_invocation_context()
        result = await pipeline.prepare(ctx)

        assert result.budget is None


# 8. No validator


class TestPrepareValidatorMissing:
    """8. Validator missing — skips validation, defaults to PASS."""

    @pytest.mark.asyncio
    async def test_pass_when_no_validator(self) -> None:
        pipeline = InvocationPipeline()
        ctx = make_invocation_context()
        result = await pipeline.prepare(ctx)

        assert result.validation.status == ValidationStatus.PASS
        assert result.validation.errors == ()


# 9. Context immutability


class TestPrepareContextImmutability:
    """9. Context immutability — original context not mutated."""

    @pytest.mark.asyncio
    async def test_original_context_not_mutated(self) -> None:
        enricher = FakeContextEnricher("new_key", "new_value")

        pipeline = InvocationPipeline(enrichers=[enricher])
        ctx = make_invocation_context()
        original_inputs = dict(ctx.dynamic_inputs)
        _ = await pipeline.prepare(ctx)

        assert ctx.dynamic_inputs == original_inputs
        assert "new_key" not in ctx.dynamic_inputs


# 10. Protocol conformance


class TestPrepareProtocolConformance:
    """10. Protocol conformance — InvocationPipeline has prepare and finalize."""

    def test_has_prepare_method(self) -> None:
        pipeline = InvocationPipeline()
        assert hasattr(pipeline, "prepare")
        assert callable(pipeline.prepare)

    def test_has_finalize_method(self) -> None:
        pipeline = InvocationPipeline()
        assert hasattr(pipeline, "finalize")
        assert callable(pipeline.finalize)
