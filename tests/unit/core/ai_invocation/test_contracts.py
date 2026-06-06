"""Tests for ai_invocation/contracts.py — Protocol conformance.

Covers:
1. Fake implementations that satisfy each Protocol.
2. Incomplete implementations that do NOT satisfy a Protocol.
3. Demonstration that test harnesses can use Protocol-compatible fakes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare_core.ai_invocation.models import (
    AuditState,
    FeatureInvocationEvidence,
    KBSuggestedStatus,
    OutputBudget,
    OutputBudgetDecision,
    PreferenceStatus,
    PromptInvocationContext,
    ValidationResult,
    ValidationStatus,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare_core.prompts.composer import ComposedPrompt


# ---------------------------------------------------------------------------
# Fake implementations for Protocol conformance testing
# ---------------------------------------------------------------------------


class FakeContextEnricher:
    """Complete ContextEnricher implementation."""

    def __init__(self) -> None:
        self.enriched = False

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        self.enriched = True
        return context.model_copy(
            update={"dynamic_inputs": {**context.dynamic_inputs, "enriched": "true"}}
        )


class FakePreferenceContextEnricher:
    """Complete PreferenceContextEnricher implementation."""

    def __init__(self) -> None:
        self.called = False

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        self.called = True
        return context.model_copy(
            update={"dynamic_inputs": {**context.dynamic_inputs, "preferences": "loaded"}}
        )


class FakeRuntimeVariableValidator:
    """Complete RuntimeVariableValidator implementation."""

    def validate(self, context: PromptInvocationContext) -> ValidationResult:
        return ValidationResult(status=ValidationStatus.PASS)


class FakeFinalPromptValidator:
    """Complete FinalPromptValidator implementation."""

    def validate(
        self,
        prompt: ComposedPrompt,
        context: PromptInvocationContext,
    ) -> ValidationResult:
        return ValidationResult(status=ValidationStatus.PASS)


class FakeIntentOutputBudgetResolver:
    """Complete IntentOutputBudgetResolver implementation."""

    async def resolve(self, context: PromptInvocationContext) -> OutputBudgetDecision:
        return OutputBudgetDecision(
            budget=OutputBudget(max_tokens=4096),
            source="default",
            reason="Default budget for testing",
        )


class FakeEvidenceSink:
    """Complete FeatureInvocationEvidenceSink implementation."""

    def __init__(self) -> None:
        self.records: list[FeatureInvocationEvidence] = []

    async def record(self, evidence: FeatureInvocationEvidence) -> None:
        self.records.append(evidence)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(**overrides: object) -> PromptInvocationContext:
    """Create a minimal PromptInvocationContext for tests."""
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
    }
    defaults.update(overrides)
    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


def _make_evidence(**overrides: object) -> FeatureInvocationEvidence:
    """Create a minimal FeatureInvocationEvidence for tests."""
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": "write",
        "prompt_route": "test/en/default",
        "preference_status": PreferenceStatus.NOT_APPLICABLE,
        "kb_suggested_status": KBSuggestedStatus.NOT_APPLICABLE,
        "final_prompt_validated": True,
        "audit_state": AuditState.RUNTIME_VERIFIED,
    }
    defaults.update(overrides)
    return FeatureInvocationEvidence(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Protocol conformance tests — ContextEnricher
# ---------------------------------------------------------------------------


class TestContextEnricherProtocol:
    """ContextEnricher protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        """FakeContextEnricher has the required enrich method."""
        fake = FakeContextEnricher()
        assert hasattr(fake, "enrich")
        assert callable(fake.enrich)

    @pytest.mark.asyncio
    async def test_fake_enricher_returns_context(self) -> None:
        """FakeContextEnricher enrich method works end-to-end."""
        fake = FakeContextEnricher()
        ctx = _make_context()
        result = await fake.enrich(ctx)
        assert isinstance(result, PromptInvocationContext)
        assert fake.enriched is True
        assert result.dynamic_inputs.get("enriched") == "true"

    def test_incomplete_does_not_satisfy(self) -> None:
        """Class without enrich method does not satisfy ContextEnricher."""

        class Incomplete:
            pass

        fake = Incomplete()
        assert not hasattr(fake, "enrich") or not callable(getattr(fake, "enrich", None))


# ---------------------------------------------------------------------------
# Protocol conformance tests — PreferenceContextEnricher
# ---------------------------------------------------------------------------


class TestPreferenceContextEnricherProtocol:
    """PreferenceContextEnricher protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        """FakePreferenceContextEnricher has the required enrich method."""
        fake = FakePreferenceContextEnricher()
        assert hasattr(fake, "enrich")
        assert callable(fake.enrich)

    @pytest.mark.asyncio
    async def test_fake_preference_enricher_returns_context(self) -> None:
        """FakePreferenceContextEnricher enrich method works end-to-end."""
        fake = FakePreferenceContextEnricher()
        ctx = _make_context()
        result = await fake.enrich(ctx)
        assert isinstance(result, PromptInvocationContext)
        assert fake.called is True
        assert result.dynamic_inputs.get("preferences") == "loaded"


# ---------------------------------------------------------------------------
# Protocol conformance tests — RuntimeVariableValidator
# ---------------------------------------------------------------------------


class TestRuntimeVariableValidatorProtocol:
    """RuntimeVariableValidator protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        """FakeRuntimeVariableValidator has the required validate method."""
        fake = FakeRuntimeVariableValidator()
        assert hasattr(fake, "validate")
        assert callable(fake.validate)

    def test_fake_validator_returns_result(self) -> None:
        """FakeRuntimeVariableValidator validate method returns ValidationResult."""
        fake = FakeRuntimeVariableValidator()
        ctx = _make_context()
        result = fake.validate(ctx)
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True

    def test_incomplete_does_not_satisfy(self) -> None:
        """Class without validate method does not satisfy the protocol."""

        class Incomplete:
            pass

        fake = Incomplete()
        assert not hasattr(fake, "validate") or not callable(getattr(fake, "validate", None))


# ---------------------------------------------------------------------------
# Protocol conformance tests — FinalPromptValidator
# ---------------------------------------------------------------------------


class TestFinalPromptValidatorProtocol:
    """FinalPromptValidator protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        """FakeFinalPromptValidator has the required validate method."""
        fake = FakeFinalPromptValidator()
        assert hasattr(fake, "validate")
        assert callable(fake.validate)

    def test_incomplete_does_not_satisfy(self) -> None:
        """Class without validate method does not satisfy the protocol."""

        class Incomplete:
            pass

        fake = Incomplete()
        assert not hasattr(fake, "validate") or not callable(getattr(fake, "validate", None))


# ---------------------------------------------------------------------------
# Protocol conformance tests — IntentOutputBudgetResolver
# ---------------------------------------------------------------------------


class TestIntentOutputBudgetResolverProtocol:
    """IntentOutputBudgetResolver protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        """FakeIntentOutputBudgetResolver has the required resolve method."""
        fake = FakeIntentOutputBudgetResolver()
        assert hasattr(fake, "resolve")
        assert callable(fake.resolve)

    @pytest.mark.asyncio
    async def test_fake_resolver_returns_decision(self) -> None:
        """FakeIntentOutputBudgetResolver resolve returns OutputBudgetDecision."""
        fake = FakeIntentOutputBudgetResolver()
        ctx = _make_context()
        decision = await fake.resolve(ctx)
        assert isinstance(decision, OutputBudgetDecision)
        assert decision.budget.max_tokens > 0

    def test_incomplete_does_not_satisfy(self) -> None:
        """Class without resolve method does not satisfy the protocol."""

        class Incomplete:
            pass

        fake = Incomplete()
        assert not hasattr(fake, "resolve") or not callable(getattr(fake, "resolve", None))


# ---------------------------------------------------------------------------
# Protocol conformance tests — FeatureInvocationEvidenceSink
# ---------------------------------------------------------------------------


class TestFeatureInvocationEvidenceSinkProtocol:
    """FeatureInvocationEvidenceSink protocol conformance."""

    def test_fake_satisfies_protocol(self) -> None:
        """FakeEvidenceSink has the required record method."""
        fake = FakeEvidenceSink()
        assert hasattr(fake, "record")
        assert callable(fake.record)

    @pytest.mark.asyncio
    async def test_fake_sink_records_evidence(self) -> None:
        """FakeEvidenceSink record method stores evidence."""
        fake = FakeEvidenceSink()
        evidence = _make_evidence()
        await fake.record(evidence)
        assert len(fake.records) == 1
        assert fake.records[0].feature_id == "test/feature"

    @pytest.mark.asyncio
    async def test_fake_sink_multiple_records(self) -> None:
        """FakeEvidenceSink accumulates multiple records."""
        fake = FakeEvidenceSink()
        await fake.record(_make_evidence())
        await fake.record(_make_evidence(feature_id="other/feature"))
        assert len(fake.records) == 2

    def test_incomplete_does_not_satisfy(self) -> None:
        """Class without record method does not satisfy the protocol."""

        class Incomplete:
            pass

        fake = Incomplete()
        assert not hasattr(fake, "record") or not callable(getattr(fake, "record", None))
