"""Protocol definitions for the AI invocation adoption contract.

Defines the interfaces that enrichers, validators, budget resolvers,
and evidence sinks must implement. All implementations are injected
via constructor (DI pattern).

No implementations live here — only contracts (RULE-03).

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-03.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from narrare_core.ai_invocation.budgets import OutputBudgetDecision
    from narrare_core.ai_invocation.models import (
        FeatureInvocationEvidence,
        PromptInvocationContext,
        ValidationResult,
    )
    from narrare_core.prompts.composer import ComposedPrompt


class ContextEnricher(Protocol):
    """Adds runtime context to an invocation before PromptComposer runs.

    Enrichers return a new :class:`PromptInvocationContext` with
    additional data. The enrichment chain runs before prompt composition
    so that templates receive populated variables.
    """

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext:
        """Enrich the invocation context with runtime data.

        Args:
            context: The current invocation context.

        Returns:
            A new PromptInvocationContext with enriched data.
        """
        ...


class PreferenceContextEnricher(ContextEnricher, Protocol):
    """Loads compact memory/preferences for the user/project pair.

    Specialized enricher that populates preference data from the memory
    layer. Uses :class:`~narrare_core.memory.protocols.PreferenceProvider`
    internally.
    """

    async def enrich(self, context: PromptInvocationContext) -> PromptInvocationContext: ...


class RuntimeVariableValidator(Protocol):
    """Validates variables against the prompt-surface and adoption contracts.

    Runs before prompt composition to catch missing required variables,
    unregistered dynamic variables, or invalid values early.
    """

    def validate(self, context: PromptInvocationContext) -> ValidationResult:
        """Validate invocation variables against declared requirements.

        Args:
            context: The invocation context to validate.

        Returns:
            ValidationResult with any errors or warnings.
        """
        ...


class FinalPromptValidator(Protocol):
    """Validates composed prompts before the model call.

    Runs after :class:`~narrare_core.prompts.composer.PromptComposer` and
    before NarrareAgent/Gateway invocation. Blocks model calls for:
    missing required variables, unsafe user-content boundaries, missing
    output-language controls, or forbidden fallbacks.
    """

    def validate(
        self,
        prompt: ComposedPrompt,
        context: PromptInvocationContext,
    ) -> ValidationResult:
        """Validate the final composed prompt.

        Args:
            prompt: The composed prompt to validate.
            context: The invocation context that produced the prompt.

        Returns:
            ValidationResult with any blocking errors or warnings.
        """
        ...


class IntentOutputBudgetResolver(Protocol):
    """Resolves output-token settings for one intent/mode invocation.

    Output limits are determined by intent/mode and settings cascade,
    not by a global default alone. Records the selected profile and
    reason for adoption evidence.
    """

    async def resolve(self, context: PromptInvocationContext) -> OutputBudgetDecision:
        """Resolve the output budget for the given invocation.

        Args:
            context: The invocation context to resolve budget for.

        Returns:
            OutputBudgetDecision with the resolved budget and provenance.
        """
        ...


class FeatureInvocationEvidenceSink(Protocol):
    """Receives runtime evidence for tests, CI probes, or observability.

    Implementations may be in-memory test sinks, structured log
    adapters, or observability adapters. Evidence is always privacy-safe.
    """

    async def record(self, evidence: FeatureInvocationEvidence) -> None:
        """Record invocation evidence.

        Args:
            evidence: Privacy-safe evidence record.
        """
        ...
