"""Shared test fixtures for InvocationPipeline tests.

Provides fake implementations of all pipeline dependencies and helper
factories used by both prepare() and finalize() test modules.

See: ADR-038, INFRA-013, CONSTRAINTS.md RULE-04/RULE-10.
"""

from __future__ import annotations

from narrare_core.ai_invocation._enums import (
    KBSuggestedRequirement,
    PreferenceRequirement,
    ValidationStatus,
)
from narrare_core.ai_invocation.budgets._types import (
    OutputBudget,
    OutputBudgetDecision,
)
from narrare_core.ai_invocation.models import (
    AdoptionPolicy,
    FeatureInvocationEvidence,
    PromptInvocationContext,
    ValidationResult,
)
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeContextEnricher:
    """Enricher that adds a key to dynamic_inputs."""

    def __init__(self, key: str, value: str) -> None:
        self._key = key
        self._value = value
        self.call_count = 0

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        self.call_count += 1
        return context.model_copy(
            update={
                "dynamic_inputs": {
                    **context.dynamic_inputs,
                    self._key: self._value,
                },
            },
        )


class NoopEnricher:
    """Enricher that returns the context unchanged."""

    def __init__(self) -> None:
        self.call_count = 0

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        self.call_count += 1
        return context


class FakeVariableValidator:
    """Validator with configurable result."""

    def __init__(self, result: ValidationResult | None = None) -> None:
        self._result = result or ValidationResult(status=ValidationStatus.PASS)
        self.call_count = 0

    def validate(self, context: PromptInvocationContext) -> ValidationResult:
        self.call_count += 1
        return self._result


class FakeFinalValidator:
    """Final validator with configurable result."""

    def __init__(self, result: ValidationResult | None = None) -> None:
        self._result = result or ValidationResult(status=ValidationStatus.PASS)

    def validate(
        self,
        prompt: ComposedPrompt,
        context: PromptInvocationContext,
    ) -> ValidationResult:
        return self._result


class FakeBudgetResolver:
    """Budget resolver returning a fixed decision."""

    def __init__(self, decision: OutputBudgetDecision | None = None) -> None:
        self._decision = decision or OutputBudgetDecision(
            budget=OutputBudget(max_tokens=4096, profile="balanced"),
            source="test",
            reason="Test budget",
        )

    async def resolve(self, context: PromptInvocationContext) -> OutputBudgetDecision:
        return self._decision


class FakeEvidenceSink:
    """Evidence sink that records evidence in a list."""

    def __init__(self) -> None:
        self.records: list[FeatureInvocationEvidence] = []

    async def record(self, evidence: FeatureInvocationEvidence) -> None:
        self.records.append(evidence)


class FailingEvidenceSink:
    """Evidence sink that always raises."""

    async def record(self, evidence: FeatureInvocationEvidence) -> None:
        raise RuntimeError("Sink unavailable")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_invocation_context(**overrides: object) -> PromptInvocationContext:
    """Create a minimal PromptInvocationContext for tests."""
    defaults: dict[str, object] = {
        "feature_id": "test/feature",
        "intent": LLMIntent.WRITE,
        "language": "en",
    }
    defaults.update(overrides)
    return PromptInvocationContext(**defaults)  # type: ignore[arg-type]


def make_adoption_policy(**overrides: object) -> AdoptionPolicy:
    """Create an AdoptionPolicy for tests."""
    defaults: dict[str, object] = {
        "preference_requirement": PreferenceRequirement.NOT_APPLICABLE,
        "kb_suggested_requirement": KBSuggestedRequirement.NOT_APPLICABLE,
    }
    defaults.update(overrides)
    return AdoptionPolicy(**defaults)  # type: ignore[arg-type]


def make_composed_prompt() -> ComposedPrompt:
    """Create a minimal ComposedPrompt for finalize() tests."""
    return ComposedPrompt(system="sys", user="usr")
