"""Invocation adapter — wraps PromptComposer.build() with pipeline prepare/finalize.

Extracts the invocation pipeline integration logic from WritingPipeline to
respect RULE-04 (file size limit).  When ``invocation_pipeline`` is ``None``,
falls back to ``composer.build()`` directly — backward compatible with callers
that have not yet been wired to the invocation contract.

When ``invocation_pipeline`` is provided but ``invocation_context`` is ``None``,
a minimal PromptInvocationContext is auto-created from the available
``intent`` and ``prompt_ctx`` data so the pipeline always runs when wired.

This module is internal to the writing subsystem — not part of the
public API.

See:
    ADR-038, INFRA-013, CONSTRAINTS.md RULE-02/RULE-04/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.shared.errors import WritingError

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)


def _create_minimal_invocation_context(
    intent: LLMIntent,
    prompt_ctx: PromptContext,
    *,
    user_id: object | None = None,
    project_id: object | None = None,
) -> PromptInvocationContext:
    """Create a minimal PromptInvocationContext from prompt data.

    Called when the invocation pipeline is wired but the caller did not
    provide an explicit invocation_context.  Derives sensible defaults
    from the intent and PromptContext that are always available in the
    writing subsystem.

    Args:
        intent: The LLM intent for this invocation.
        prompt_ctx: The prompt context carrying language, mode, etc.
        user_id: Optional user identifier for enrichment.
        project_id: Optional project identifier for enrichment.

    Returns:
        A PromptInvocationContext with feature_id derived from the intent.
    """
    from uuid import uuid4

    from narrare_core.ai_invocation.models import PromptInvocationContext

    return PromptInvocationContext(
        feature_id=f"writing_{intent.value}",
        intent=intent,
        mode=prompt_ctx.mode,
        user_id=user_id,
        project_id=project_id,
        language=prompt_ctx.language,
        output_language=prompt_ctx.writing_language or None,
        invocation_id=uuid4(),
        streaming=True,
    )


async def build_and_validate_prompt(
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    intent: LLMIntent,
    prompt_ctx: PromptContext,
    invocation_context: PromptInvocationContext | None = None,
    *,
    user_id: object | None = None,
    project_id: object | None = None,
) -> ComposedPrompt:
    """Build a prompt, optionally wrapping with invocation pipeline steps.

    When ``invocation_pipeline`` is ``None``, falls back to
    ``composer.build()`` directly (backward compatible).

    When ``invocation_pipeline`` is provided:
        - If ``invocation_context`` is also provided, uses it directly.
        - If ``invocation_context`` is ``None``, auto-creates a minimal
          context from ``intent``, ``prompt_ctx``, and optional
          ``user_id``/``project_id``.
        1. ``prepare()`` — validate variables + enrich + resolve budget.
        2. Merge prepared ``dynamic_inputs`` into ``prompt_ctx`` (ADR-045
           Decision 3) and build the prompt from the *merged* context.
           Caller-provided fields win over enricher suggestions (RULE-22).
        3. ``finalize()`` — validate final prompt + record evidence.
        4. Return the composed prompt.

    Args:
        composer: PromptComposer instance for building prompts.
        invocation_pipeline: Optional InvocationPipeline for validation.
        intent: LLM intent determining the prompt template.
        prompt_ctx: Prompt context with template variables.
        invocation_context: Optional typed context for the invocation.
        user_id: Optional user identifier for the invocation context.
        project_id: Optional project identifier for the invocation context.

    Returns:
        ComposedPrompt ready for LLM consumption.

    Raises:
        WritingError: If pre-composition or final validation fails.
    """
    if invocation_pipeline is None:
        return await composer.build(intent, prompt_ctx)

    # Auto-create context when pipeline is wired but context was not provided.
    ctx = invocation_context or _create_minimal_invocation_context(
        intent,
        prompt_ctx,
        user_id=user_id,
        project_id=project_id,
    )

    # Phase 1: Prepare — validate + enrich + resolve budget
    prepared = await invocation_pipeline.prepare(ctx)

    if not prepared.validation.is_valid:
        errors = ", ".join(prepared.validation.errors)
        logger.warning(
            "invocation_pre_composition_validation_failed",
            feature_id=ctx.feature_id,
            errors=errors,
        )
        raise WritingError(
            f"Pre-composition validation failed: {errors}",
            code="INVOCATION_VALIDATION_FAILED",
        )

    # Phase 2: Merge prepared dynamic_inputs into prompt_ctx (ADR-045
    # Decision 3) and compose from the merged context. Empty caller fields
    # are filled by enrichment; non-empty fields are preserved (RULE-22
    # precedence: caller > enricher). This mirrors the non-writing adapter
    # (compose_invocation) so both domains apply the same merge contract.
    from narrare_core.ai_invocation.prompt_context_merge import (
        merge_prepared_dynamic_inputs,
    )

    merged_ctx = merge_prepared_dynamic_inputs(prompt_ctx, prepared.context).context
    prompt = await composer.build(intent, merged_ctx)

    # Phase 3: Finalize — validate final prompt + record evidence
    finalized = await invocation_pipeline.finalize(
        prompt,
        ctx,
        prepared=prepared,
    )

    if not finalized.validation.is_valid:
        errors = ", ".join(finalized.validation.errors)
        logger.warning(
            "invocation_final_validation_failed",
            feature_id=ctx.feature_id,
            errors=errors,
        )
        raise WritingError(
            f"Final prompt validation failed: {errors}",
            code="INVOCATION_FINAL_VALIDATION_FAILED",
        )

    return prompt
