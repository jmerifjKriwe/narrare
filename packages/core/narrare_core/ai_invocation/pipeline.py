"""Invocation pipeline — orchestrates enrichment, validation, budget, and evidence.

Ties together the standalone P0.3 components (enricher, variable validator,
budget resolver, final validator, evidence sink) into a two-phase pipeline
that wraps around :class:`~narrare_core.prompts.composer.PromptComposer`.

Phase 1 — ``prepare()``:
    Variable validation → sequential enrichment → budget resolution.

Phase 2 — ``finalize()``:
    Final prompt validation → evidence recording.

The pipeline is **stateless** and safe for concurrent use. All dependencies
are injected via the constructor. When a component is ``None``, its step
is silently skipped.

Never raises — both methods always return a result model.

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06/RULE-10/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, ConfigDict

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import (
    ContextEnrichmentResult,
    FeatureInvocationEvidence,
    PromptInvocationContext,
    ValidationResult,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare_core.ai_invocation.budgets._types import OutputBudgetDecision
    from narrare_core.ai_invocation.contracts import (
        ContextEnricher,
        FeatureInvocationEvidenceSink,
        FinalPromptValidator,
        IntentOutputBudgetResolver,
        RuntimeVariableValidator,
    )
    from narrare_core.prompts.composer import ComposedPrompt

logger = structlog.get_logger(__name__)


class PreparedInvocation(BaseModel):
    """Result of the ``prepare()`` phase — enriched context and validation state.

    Attributes:
        context: The (possibly enriched) invocation context.
        budget: Resolved output budget, or ``None`` if no resolver was provided.
        validation: Variable validation result (PASS if no validator).
        enrichment_result: Enrichment metadata, or ``None`` if no enrichers.
    """

    model_config = ConfigDict(frozen=True)

    context: PromptInvocationContext
    budget: OutputBudgetDecision | None = None
    validation: ValidationResult
    enrichment_result: ContextEnrichmentResult | None = None


class FinalizedInvocation(BaseModel):
    """Result of the ``finalize()`` phase — final validation and evidence state.

    Attributes:
        validation: Final prompt validation result (PASS if no validator).
        evidence_recorded: Whether evidence was successfully sent to the sink.
    """

    model_config = ConfigDict(frozen=True)

    validation: ValidationResult
    evidence_recorded: bool = False


class InvocationPipeline:
    """Orchestrates the AI invocation adoption pipeline.

    Stateless — stores only injected dependencies. Safe for concurrent use.
    All steps are optional; when a component is ``None``, its step is skipped.

    Args:
        enrichers: Ordered sequence of context enrichers. Each enricher
            receives the output of the previous one.
        variable_validator: Pre-composition variable validator. If the
            result is FAIL, enrichment and budget resolution are skipped.
        budget_resolver: Output budget resolver for the invocation.
        final_validator: Post-composition prompt validator.
        evidence_sink: Receives invocation evidence for observability.
    """

    def __init__(
        self,
        *,
        enrichers: Sequence[ContextEnricher] = (),
        variable_validator: RuntimeVariableValidator | None = None,
        budget_resolver: IntentOutputBudgetResolver | None = None,
        final_validator: FinalPromptValidator | None = None,
        evidence_sink: FeatureInvocationEvidenceSink | None = None,
    ) -> None:
        self._enrichers = tuple(enrichers)
        self._variable_validator = variable_validator
        self._budget_resolver = budget_resolver
        self._final_validator = final_validator
        self._evidence_sink = evidence_sink

    async def prepare(
        self,
        context: PromptInvocationContext,
    ) -> PreparedInvocation:
        """Run pre-composition steps: validate, enrich, resolve budget.

        Steps:
            1. Variable validation (if validator provided). On FAIL,
               returns early — no enrichment or budget resolution.
            2. Sequential enrichment. Each enricher receives the output
               of the previous one. Tracks which fields changed.
            3. Budget resolution (if resolver provided).

        Never raises — always returns a :class:`PreparedInvocation`.

        Args:
            context: The invocation context to prepare.

        Returns:
            PreparedInvocation with enriched context, budget, and validation.
        """
        # Step 1: Variable validation
        validation = self._validate_variables(context)
        if not validation.is_valid:
            logger.info(
                "pipeline_variable_validation_failed",
                feature_id=context.feature_id,
                errors=validation.errors,
            )
            return PreparedInvocation(
                context=context,
                budget=None,
                validation=validation,
                enrichment_result=None,
            )

        # Step 2: Sequential enrichment
        enriched_context, enrichment_result = await self._run_enrichers(context)

        # Step 3: Budget resolution
        budget = await self._resolve_budget(enriched_context)

        logger.debug(
            "pipeline_prepare_complete",
            feature_id=context.feature_id,
            has_budget=budget is not None,
            enrichment_fields=(
                enrichment_result.enriched_fields if enrichment_result else frozenset()
            ),
        )

        return PreparedInvocation(
            context=enriched_context,
            budget=budget,
            validation=validation,
            enrichment_result=enrichment_result,
        )

    async def finalize(
        self,
        prompt: ComposedPrompt,
        context: PromptInvocationContext,
        *,
        prepared: PreparedInvocation | None = None,
    ) -> FinalizedInvocation:
        """Run post-composition steps: validate prompt, record evidence.

        Steps:
            1. Final prompt validation (if validator provided).
            2. Build and record :class:`FeatureInvocationEvidence` (if sink
               provided). Evidence recording failures are logged but do not
               block the invocation.

        Never raises — always returns a :class:`FinalizedInvocation`.

        Args:
            prompt: The composed prompt to validate.
            context: The invocation context that produced the prompt.
            prepared: Optional prepared invocation from the ``prepare()``
                phase. Used for evidence metadata (budget profile, variable
                validation errors).

        Returns:
            FinalizedInvocation with validation result and evidence state.
        """
        # Step 1: Final prompt validation
        final_validation, final_validator_ran = self._validate_final_prompt(prompt, context)

        if not final_validation.is_valid:
            logger.info(
                "pipeline_final_validation_failed",
                feature_id=context.feature_id,
                errors=final_validation.errors,
            )

        # Step 2: Evidence recording
        evidence_recorded = await self._record_evidence(
            context=context,
            prepared=prepared,
            final_validation=final_validation,
            final_validator_ran=final_validator_ran,
        )

        logger.debug(
            "pipeline_finalize_complete",
            feature_id=context.feature_id,
            evidence_recorded=evidence_recorded,
            final_status=final_validation.status,
        )

        return FinalizedInvocation(
            validation=final_validation,
            evidence_recorded=evidence_recorded,
        )

    # ------------------------------------------------------------------
    # Private helpers — each handles one step
    # ------------------------------------------------------------------

    def _validate_variables(
        self,
        context: PromptInvocationContext,
    ) -> ValidationResult:
        """Run variable validation if a validator is configured."""
        if self._variable_validator is None:
            return ValidationResult(status=ValidationStatus.PASS)
        logger.debug(
            "pipeline_validating_variables",
            feature_id=context.feature_id,
        )
        return self._variable_validator.validate(context)

    async def _run_enrichers(
        self,
        context: PromptInvocationContext,
    ) -> tuple[PromptInvocationContext, ContextEnrichmentResult | None]:
        """Run enrichers in sequence, tracking field changes."""
        if not self._enrichers:
            return context, None

        current = context
        all_enriched_fields: set[str] = set()
        sources: list[tuple[str, str]] = []

        for idx, enricher in enumerate(self._enrichers):
            before_inputs = current.dynamic_inputs
            before_context = current

            logger.debug(
                "pipeline_running_enricher",
                feature_id=context.feature_id,
                enricher_index=idx,
            )
            current = await enricher.enrich(current)

            # Track which dynamic_inputs keys changed or were added
            after_inputs = current.dynamic_inputs
            changed_keys = set(after_inputs.keys()) - set(before_inputs.keys())
            # Also detect value changes for existing keys
            for key in set(before_inputs.keys()) & set(after_inputs.keys()):
                if before_inputs[key] != after_inputs[key]:
                    changed_keys.add(key)
            all_enriched_fields.update(changed_keys)

            if current != before_context:
                sources.append((f"enricher_{idx}", "ran"))

        enrichment_result = ContextEnrichmentResult(
            enriched_fields=frozenset(all_enriched_fields),
            enrichment_sources=tuple(sources),
        )
        return current, enrichment_result

    async def _resolve_budget(
        self,
        context: PromptInvocationContext,
    ) -> OutputBudgetDecision | None:
        """Resolve output budget if a resolver is configured."""
        if self._budget_resolver is None:
            return None
        logger.debug(
            "pipeline_resolving_budget",
            feature_id=context.feature_id,
        )
        return await self._budget_resolver.resolve(context)

    def _validate_final_prompt(
        self,
        prompt: ComposedPrompt,
        context: PromptInvocationContext,
    ) -> tuple[ValidationResult, bool]:
        """Run final prompt validation if a validator is configured.

        Returns:
            Tuple of (validation result, whether the validator actually ran).
        """
        if self._final_validator is None:
            return ValidationResult(status=ValidationStatus.PASS), False
        logger.debug(
            "pipeline_validating_final_prompt",
            feature_id=context.feature_id,
        )
        return self._final_validator.validate(prompt, context), True

    async def _record_evidence(
        self,
        context: PromptInvocationContext,
        prepared: PreparedInvocation | None,
        final_validation: ValidationResult,
        final_validator_ran: bool,
    ) -> bool:
        """Build and record evidence. Returns True if recorded successfully."""
        if self._evidence_sink is None:
            return False

        evidence = self._build_evidence(
            context,
            prepared,
            final_validation,
            final_validator_ran,
        )

        try:
            await self._evidence_sink.record(evidence)
            return True
        except Exception:
            logger.warning(
                "pipeline_evidence_recording_failed",
                feature_id=context.feature_id,
                exc_info=True,
            )
            return False

    def _build_evidence(
        self,
        context: PromptInvocationContext,
        prepared: PreparedInvocation | None,
        final_validation: ValidationResult,
        final_validator_ran: bool,
    ) -> FeatureInvocationEvidence:
        """Build a privacy-safe evidence record from pipeline state."""
        from narrare_core.ai_invocation._evidence import build_invocation_evidence

        return build_invocation_evidence(
            context=context,
            prepared=prepared,
            final_validation=final_validation,
            final_validator_ran=final_validator_ran,
        )


def _rebuild_forward_refs() -> None:
    """Resolve Pydantic forward refs after moving type imports under TYPE_CHECKING."""
    from narrare_core.ai_invocation.budgets._types import OutputBudgetDecision

    PreparedInvocation.model_rebuild(
        _types_namespace={"OutputBudgetDecision": OutputBudgetDecision},
    )


_rebuild_forward_refs()
