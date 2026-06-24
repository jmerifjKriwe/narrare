"""Invocation adapter — delegates pipeline orchestration to compose_invocation().

Extracts the invocation pipeline integration logic from WritingPipeline to
respect RULE-04 (file size limit). Delegates the full prepare → merge →
compose → finalize cycle to
:func:`~narrare_core.ai_invocation.non_writing_adapter.compose_invocation`
(ADR-048 Q2), keeping only writing-specific conveniences:

- Auto-create :class:`PromptInvocationContext` when not provided.
- Wrap :class:`InvocationValidationError` as :class:`WritingError`
  (writing-domain error contract).

When ``invocation_pipeline`` is ``None``, ``compose_invocation()`` falls back
to ``composer.build()`` directly — backward compatible with callers that have
not yet been wired to the invocation contract.

This module is internal to the writing subsystem — not part of the
public API.

See:
    ADR-038, ADR-048 Q2, INFRA-013, CONSTRAINTS.md RULE-02/RULE-04/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.ai_invocation.non_writing_adapter import compose_invocation
from narrare_core.shared.errors import InvocationValidationError, WritingError

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
    from narrare_core.prompts.context import PromptContext


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
    """Build a writing prompt, delegating pipeline orchestration to compose_invocation().

    Writing-specific responsibilities:
    - Auto-create PromptInvocationContext when not provided (writing convenience).
    - Wrap InvocationValidationError as WritingError (writing error contract).

    Delegated to compose_invocation() (ADR-048):
    - prepare → merge → compose → finalize cycle.
    - Enrichment (preferences, kb_suggested, budget resolution).
    - Evidence recording with real prompt fingerprint.

    The WritingContextAssembler KB-tiering happens BEFORE this function is called
    (in the WritingPipeline / caller). The assembled KB context is already in
    prompt_ctx. This function does NOT own KB-tiering.

    Args:
        composer: PromptComposer instance for building prompts.
        invocation_pipeline: Optional InvocationPipeline for validation/evidence.
        intent: LLM intent determining the prompt template.
        prompt_ctx: Prompt context with template variables (KB context already assembled).
        invocation_context: Optional typed context for the invocation.
        user_id: Optional user identifier for the invocation context.
        project_id: Optional project identifier for the invocation context.

    Returns:
        ComposedPrompt ready for LLM consumption.

    Raises:
        WritingError: If pre-composition or final validation fails (wraps
            InvocationValidationError from compose_invocation).
    """
    # Auto-create context when pipeline is wired but context was not provided.
    ctx = invocation_context or _create_minimal_invocation_context(
        intent,
        prompt_ctx,
        user_id=user_id,
        project_id=project_id,
    )

    try:
        result = await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=ctx,
            composer=composer,
            prompt_context=prompt_ctx,
            intent=intent,
        )
    except InvocationValidationError as exc:
        raise WritingError(
            str(exc),
            code=exc.code if exc.code else "INVOCATION_VALIDATION_FAILED",
        ) from exc

    # Mode 1 (composer-driven) always sets composed_prompt; assert narrows
    # the Optional[ComposedPrompt] to ComposedPrompt for the type checker.
    assert result.composed_prompt is not None
    return result.composed_prompt
