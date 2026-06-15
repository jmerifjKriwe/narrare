"""Domain-agnostic invocation adapter for non-writing AI calls.

Orchestrates the full prepare -> merge -> compose -> finalize cycle through the
:class:`~narrare_core.ai_invocation.pipeline.InvocationPipeline`. This is the canonical
path for analysis, kb, planning, chat, and any future non-writing domain (ADR-048).

The writing subsystem keeps its own specialised adapter
(``writing/_invocation_adapter.py``) because it imports :class:`WritingError` and
owns tiered KB context budgeting. Non-writing domains use this public adapter
instead (RULE-05).

Supports two composition modes:

- **Mode 1 (composer-driven)**: the service provides a
  :class:`~narrare_core.prompts.composer.PromptComposer` and
  :class:`~narrare_core.prompts.context.PromptContext`. The adapter merges prepared
  enrichment into the context via
  :func:`~narrare_core.ai_invocation.prompt_context_merge.merge_prepared_dynamic_inputs`
  (ADR-045 Decision 3), composes the real prompt, and finalizes with the
  real :class:`~narrare_core.prompts.composer.ComposedPrompt`.

- **Mode 2 (agent-internal)**: the service provides a
  :class:`~narrare_core.ai_invocation.manual_injection.ManualInjectionDeclaration`.
  The adapter runs prepare and finalize but skips composition (the agent owns it).
  Finalize receives a typed marker derived from the declaration -- not a placeholder.

See:
    ADR-048, ADR-045 Decision 3/7,
    CONSTRAINTS.md RULE-02a/RULE-03/RULE-05/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, ConfigDict

from narrare_core.ai_invocation._enums import ValidationStatus
from narrare_core.ai_invocation.models import PromptInvocationContext, ValidationResult
from narrare_core.ai_invocation.pipeline import (
    FinalizedInvocation,
    InvocationPipeline,
    PreparedInvocation,
)
from narrare_core.ai_invocation.prompt_context_merge import (
    merge_prepared_dynamic_inputs,
)
from narrare_core.shared.errors import InvocationValidationError

if TYPE_CHECKING:
    from narrare_core.ai_invocation.budgets._types import OutputBudgetDecision
    from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Manual-injection marker system prompt.
# ---------------------------------------------------------------------------
# Unlike the deprecated placeholder ``"[analysis-kb-invocation]"``, this marker
# is a structured, typed sentinel. The user-channel payload encodes the declared
# variable names and injection mechanism so the evidence fingerprint is
# deterministic per-declaration and privacy-safe (no raw content).
_MANUAL_INJECTION_MARKER_SYSTEM = "[manual-injection:agent-internal]"


class ComposedInvocation(BaseModel):
    """Result of composing an invocation through the pipeline.

    Carries everything the service needs to call the agent:

    - The composed prompt (Mode 1) or ``None`` (Mode 2 -- agent owns composition).
    - The merged :class:`PromptContext` (enrichment applied) -- useful for agent
      deps. ``None`` when no ``prompt_context`` was provided (Mode 2 without a
      caller context).
    - The prepared invocation (enriched context, budget, validation).
    - The finalized invocation (final validation, evidence state).
    - The resolved output budget -- for run-limit enforcement (ADR-045 Decision 4).
    - The manual-injection declaration (Mode 2 only).
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    composed_prompt: ComposedPrompt | None
    merged_context: PromptContext | None
    prepared: PreparedInvocation
    finalized: FinalizedInvocation
    budget: OutputBudgetDecision | None = None
    manual_injection: ManualInjectionDeclaration | None = None

    @property
    def is_composer_driven(self) -> bool:
        """True when Mode 1 (prompt composed by PromptComposer)."""
        return self.composed_prompt is not None

    @property
    def is_agent_internal(self) -> bool:
        """True when Mode 2 (prompt composed by the agent internally)."""
        return self.manual_injection is not None


# ---------------------------------------------------------------------------
# compose_invocation — domain-agnostic adapter (Mode 1 composer-driven OR Mode 2 agent-internal)
# ---------------------------------------------------------------------------


async def compose_invocation(
    *,
    invocation_pipeline: InvocationPipeline | None,
    invocation_context: PromptInvocationContext,
    composer: PromptComposer | None = None,
    prompt_context: PromptContext | None = None,
    intent: LLMIntent | None = None,
    manual_injection: ManualInjectionDeclaration | None = None,
) -> ComposedInvocation:
    """Compose an invocation through the pipeline: prepare -> merge -> compose -> finalize.

    This is the domain-agnostic counterpart to the writing adapter's
    ``build_and_validate_prompt()``. It serves analysis, kb, planning, chat,
    and any future non-writing domain.

    **Mode 1 -- Composer-driven** (``composer`` + ``prompt_context`` + ``intent``):
        1. ``prepare()`` -- validate variables, enrich (preferences, kb_suggested, etc.),
           resolve budget.
        2. Merge prepared ``dynamic_inputs`` into ``prompt_context`` via
           ``merge_prepared_dynamic_inputs()`` (ADR-045 Decision 3).
        3. Compose the real prompt via ``composer.build(intent, merged_context)``.
        4. ``finalize()`` -- validate the REAL composed prompt, record correlated evidence.
        5. Return ``ComposedInvocation`` with ``composed_prompt`` set.

    **Mode 2 -- Agent-internal** (``manual_injection`` declaration, no composer):
        1. ``prepare()`` -- validate, enrich, resolve budget.
        2. Merge prepared ``dynamic_inputs`` into ``prompt_context`` (if provided) so
           the service can pass enrichment to agent deps.
        3. Skip composition -- the agent owns it.
        4. ``finalize()`` -- record evidence with a typed manual-injection marker
           (NOT a placeholder prompt). The marker carries the declared variable names
           and injection mechanism.
        5. Return ``ComposedInvocation`` with ``composed_prompt=None``,
           ``manual_injection`` set.

    **Backward compatibility** -- ``invocation_pipeline is None``:
        Mode 1: falls back to ``composer.build(intent, prompt_context)`` directly
        (no merge, no finalize). This preserves the pre-pipeline behavior.
        Mode 2: returns a minimal ``ComposedInvocation`` with no-op prepared/finalized.

    Args:
        invocation_pipeline: The InvocationPipeline, or ``None`` for backward-compatible
            fallback (no enrichment, no evidence).
        invocation_context: Typed request-scoped context (feature_id, intent, user_id,
            project_id, language, etc.). Built by the service or via
            ``build_invocation_context()``.
        composer: PromptComposer for Mode 1. Must be ``None`` for Mode 2.
        prompt_context: PromptContext for Mode 1. Optional for Mode 2 (used only to
            carry merged enrichment to agent deps).
        intent: LLMIntent for Mode 1 (passed to composer). Optional for Mode 2
            (inferred from ``invocation_context``).
        manual_injection: ManualInjectionDeclaration for Mode 2. Must be ``None`` for Mode 1.

    Returns:
        ComposedInvocation carrying the composed prompt (Mode 1), merged context,
        prepared/finalized state, and resolved budget.

    Raises:
        InvocationValidationError: If pre-composition or final validation fails
            (Mode 1, when pipeline is provided and validation is FAIL).
        ValueError: If both ``composer`` and ``manual_injection`` are provided, or
            neither; or if Mode 1 is missing ``intent`` or ``prompt_context``.
    """
    # ------------------------------------------------------------------
    # Mode resolution
    # ------------------------------------------------------------------
    if composer is not None and manual_injection is not None:
        raise ValueError(
            "compose_invocation: provide 'composer' (Mode 1) OR "
            "'manual_injection' (Mode 2), not both."
        )
    if composer is None and manual_injection is None:
        raise ValueError(
            "compose_invocation: must provide either 'composer' (Mode 1) "
            "or 'manual_injection' (Mode 2)."
        )

    is_mode1 = composer is not None

    # Mode 1 requires intent and prompt_context
    if is_mode1:
        if intent is None:
            raise ValueError("compose_invocation Mode 1 requires 'intent' (passed to composer).")
        if prompt_context is None:
            raise ValueError("compose_invocation Mode 1 requires 'prompt_context'.")

    # ------------------------------------------------------------------
    # Backward compatibility: no pipeline wired
    # ------------------------------------------------------------------
    if invocation_pipeline is None:
        return await _compose_without_pipeline(
            invocation_context=invocation_context,
            composer=composer,
            prompt_context=prompt_context,
            intent=intent,
            manual_injection=manual_injection,
        )

    # ------------------------------------------------------------------
    # Phase 1: Prepare -- validate + enrich + resolve budget
    # ------------------------------------------------------------------
    prepared = await invocation_pipeline.prepare(invocation_context)

    if not prepared.validation.is_valid:
        errors = ", ".join(prepared.validation.errors)
        logger.warning(
            "invocation_pre_composition_validation_failed",
            feature_id=invocation_context.feature_id,
            errors=errors,
        )
        raise InvocationValidationError(
            f"Pre-composition validation failed: {errors}",
            code="INVOCATION_VALIDATION_FAILED",
        )

    # ------------------------------------------------------------------
    # Phase 2: Merge enrichment into PromptContext (ADR-045 Decision 3)
    # ------------------------------------------------------------------
    merged_context: PromptContext | None = None
    if prompt_context is not None:
        merge_result = merge_prepared_dynamic_inputs(
            prompt_context,
            prepared.context,
        )
        merged_context = merge_result.context

    # ------------------------------------------------------------------
    # Phase 3: Compose (Mode 1) or skip (Mode 2)
    # ------------------------------------------------------------------
    composed_prompt: ComposedPrompt | None = None
    if is_mode1:
        assert composer is not None  # narrows for type-checker
        assert intent is not None
        assert merged_context is not None
        composed_prompt = await composer.build(intent, merged_context)

    # ------------------------------------------------------------------
    # Phase 4: Finalize -- validate prompt + record evidence
    # ------------------------------------------------------------------
    if composed_prompt is not None:
        finalize_prompt: ComposedPrompt = composed_prompt
    else:
        assert manual_injection is not None
        finalize_prompt = _manual_injection_marker(manual_injection)

    finalized = await invocation_pipeline.finalize(
        finalize_prompt,
        invocation_context,
        prepared=prepared,
    )

    # ------------------------------------------------------------------
    # Phase 5: Mode 1 final validation gate
    # ------------------------------------------------------------------
    if is_mode1 and not finalized.validation.is_valid:
        errors = ", ".join(finalized.validation.errors)
        logger.warning(
            "invocation_final_validation_failed",
            feature_id=invocation_context.feature_id,
            errors=errors,
        )
        raise InvocationValidationError(
            f"Final prompt validation failed: {errors}",
            code="INVOCATION_FINAL_VALIDATION_FAILED",
        )

    return ComposedInvocation(
        composed_prompt=composed_prompt,
        merged_context=merged_context,
        prepared=prepared,
        finalized=finalized,
        budget=prepared.budget,
        manual_injection=manual_injection,
    )


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _manual_injection_marker(
    declaration: ManualInjectionDeclaration,
) -> ComposedPrompt:
    """Build a typed marker prompt for agent-internal composition evidence.

    Unlike the deprecated placeholder (``"[analysis-kb-invocation]"``), this
    marker is deterministic per-declaration: it encodes the declared variable
    names and injection mechanism. The resulting evidence fingerprint is
    privacy-safe (no raw content) and uniquely tied to the declaration.
    """
    from narrare_core.prompts.composer import ComposedPrompt

    return ComposedPrompt(
        system=_MANUAL_INJECTION_MARKER_SYSTEM,
        user=(
            f"[composed-by-agent] "
            f"variables={list(declaration.variables)} "
            f"mechanism={declaration.injection_mechanism} "
            f"precedence={declaration.precedence_level}"
        ),
    )


async def _compose_without_pipeline(
    *,
    invocation_context: PromptInvocationContext,
    composer: PromptComposer | None,
    prompt_context: PromptContext | None,
    intent: LLMIntent | None,
    manual_injection: ManualInjectionDeclaration | None,
) -> ComposedInvocation:
    """Backward-compatible path when no InvocationPipeline is wired.

    Mode 1: calls ``composer.build()`` directly (no merge, no evidence).
    Mode 2: returns a minimal result with no-op prepared/finalized state.
    """
    noop_prepared = PreparedInvocation(
        context=invocation_context,
        budget=None,
        validation=ValidationResult(status=ValidationStatus.PASS),
        enrichment_result=None,
    )
    noop_finalized = FinalizedInvocation(
        validation=ValidationResult(status=ValidationStatus.PASS),
        evidence_recorded=False,
    )

    if composer is not None:
        assert prompt_context is not None
        assert intent is not None
        composed = await composer.build(intent, prompt_context)
        return ComposedInvocation(
            composed_prompt=composed,
            merged_context=prompt_context,
            prepared=noop_prepared,
            finalized=noop_finalized,
            budget=None,
            manual_injection=None,
        )

    # Mode 2 without pipeline
    assert manual_injection is not None
    return ComposedInvocation(
        composed_prompt=None,
        merged_context=prompt_context,
        prepared=noop_prepared,
        finalized=noop_finalized,
        budget=None,
        manual_injection=manual_injection,
    )


# ------------------------------------------------------------------
# Forward-ref resolution (PromptContext / ComposedPrompt are dataclasses)
# ------------------------------------------------------------------


def _rebuild_forward_refs() -> None:
    """Resolve Pydantic forward refs for ComposedInvocation fields."""
    from narrare_core.ai_invocation.budgets._types import OutputBudgetDecision
    from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration
    from narrare_core.prompts.composer import ComposedPrompt
    from narrare_core.prompts.context import PromptContext

    ComposedInvocation.model_rebuild(
        _types_namespace={
            "ComposedPrompt": ComposedPrompt,
            "PromptContext": PromptContext,
            "OutputBudgetDecision": OutputBudgetDecision,
            "ManualInjectionDeclaration": ManualInjectionDeclaration,
        },
    )


_rebuild_forward_refs()
