"""Chat invocation preparation (ADR-045 / ADR-048 Mode 2).

ChatAgent composes its prompt internally from ``ChatDeps`` (PromptComposer
cascade) and ``ProcessHistory`` (ADR-034). This module owns the invocation
preparation for that agent-internal streaming path:

- :func:`compose_chat_invocation` runs ``compose_invocation()`` (Mode 2) for
  correlated evidence and resolves enrichment (kb_suggested,
  user_preferences) into the merged context that flows to ``ChatDeps``.
- :func:`resolve_chat_run_limits` converts output budgets into pydantic-ai
  run limits (ADR-045 Decision 4).

Both helpers degrade gracefully: a ``None`` pipeline / resolver is a no-op,
and compose failures are logged so the chat keeps working (RULE-11).

Extracted from ``chat_service.py`` for RULE-04 (300-line service limit).
One responsibility (RULE-06): prepare the chat invocation + run limits.

See: ADR-045, ADR-048, CONSTRAINTS.md RULE-02a/RULE-03/RULE-06/RULE-11/RULE-13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.ai_invocation import ManualInjectionDeclaration, compose_invocation
from narrare_core.llm.run_limits import merge_model_settings

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.non_writing_adapter import ComposedInvocation
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)

CHAT_FEATURE_ID = "chat"

# ADR-048 Mode 2 declaration (agent-internal composition).
# ChatAgent composes its prompt internally from ChatDeps (PromptComposer cascade)
# and ProcessHistory message history (ADR-034). The invocation pipeline records
# correlated evidence and resolves enrichment (kb_suggested, user_preferences)
# into the merged context that flows to ChatDeps.
CHAT_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "ChatAgent composes its prompt internally from ChatDeps "
        "(PromptComposer cascade) and ProcessHistory message history."
    ),
    variables=("kb_suggested", "user_preferences"),
    injection_mechanism="agent_deps",
)


def build_chat_invocation_context(
    *,
    prompt_ctx: PromptContext,
    user_id: UUID,
    project_id: UUID | None,
    conv_id: UUID,
    invocation_id: UUID,
) -> PromptInvocationContext:
    """Build the ``PromptInvocationContext`` for a chat invocation.

    ADR-045 Decision 6: user and project IDs are mandatory in the invocation
    context. The conversation ID is carried as a dynamic input so enrichers
    and evidence can correlate it. ``streaming=True`` signals the streaming
    path (RULE-13).

    Args:
        prompt_ctx: The composed chat prompt context.
        user_id: The authenticated user's UUID.
        project_id: The project UUID for enrichment correlation, or
            ``None`` for project-less chat (NOTES-001 §6b).
        conv_id: The conversation UUID.
        invocation_id: The per-turn invocation UUID.

    Returns:
        A ``PromptInvocationContext`` ready for ``compose_invocation()``.
    """
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.llm.intents import LLMIntent

    return PromptInvocationContext(
        feature_id=CHAT_FEATURE_ID,
        intent=LLMIntent.CHAT,
        invocation_id=invocation_id,
        user_id=user_id,
        project_id=project_id,
        language=prompt_ctx.language,
        streaming=True,
        dynamic_inputs={"conversation_id": str(conv_id)},
        prompt_context=prompt_ctx,
    )


async def compose_chat_invocation(
    *,
    invocation_pipeline: InvocationPipeline | None,
    prompt_ctx: PromptContext,
    user_id: UUID,
    project_id: UUID | None,
    conv_id: UUID,
    invocation_id: UUID,
) -> PromptContext:
    """Compose the chat invocation (Mode 2) and return the enriched context.

    Runs ``compose_invocation()`` for correlated evidence + enrichment, then
    returns the merged context (kb_suggested, user_preferences applied) that
    flows to ``ChatDeps``. Failures are logged and degraded to the original
    context so the chat keeps working (RULE-11). When ``invocation_pipeline``
    is ``None`` the compose is a no-op and the original context is returned
    (backward compatible).

    Args:
        invocation_pipeline: The InvocationPipeline, or ``None`` for a no-op.
        prompt_ctx: The original chat prompt context.
        user_id: The authenticated user's UUID.
        project_id: The project UUID for enrichment correlation, or
            ``None`` for project-less chat (NOTES-001 §6b).
        conv_id: The conversation UUID.
        invocation_id: The per-turn invocation UUID.

    Returns:
        The enriched ``PromptContext`` (or the original on failure / no-op).
    """
    invocation_ctx = build_chat_invocation_context(
        prompt_ctx=prompt_ctx,
        user_id=user_id,
        project_id=project_id,
        conv_id=conv_id,
        invocation_id=invocation_id,
    )
    try:
        composed: ComposedInvocation = await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=invocation_ctx,
            prompt_context=prompt_ctx,
            manual_injection=CHAT_MANUAL_INJECTION,
        )
    except Exception:
        logger.warning(
            "chat_invocation_compose_failed",
            conversation_id=str(conv_id),
            exc_info=True,
        )
        return prompt_ctx
    if composed.merged_context is not None:
        return composed.merged_context
    return prompt_ctx


def resolve_chat_run_limits(
    *,
    resolver: DefaultRunLimitResolver | None,
    config: ResolvedModelConfig,
    invocation_id: UUID,
    base_model_settings: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Resolve pydantic-ai run/stream kwargs for output-budget enforcement.

    Mirrors ``WritingTurnService`` (ADR-045 Decision 4): resolves
    provider-safe ``UsageLimits`` and ``model_settings`` from the resolved
    model config. Returns an empty dict when no resolver is wired and no
    base settings are given (backward compatible).

    Task 6d-1: ``base_model_settings`` carries the assembly point's
    intent-aware runtime settings (``prepared.model_settings`` from
    ``ModelRegistry.prepare``). They form the merge BASE; the resolver's
    per-turn output-budget ``max_tokens`` is layered on top, keeping the
    resolver authoritative on key conflicts (ADR-045 Decision 4).

    Args:
        resolver: The run-limit resolver, or ``None`` for no enforcement.
        config: The resolved model configuration.
        invocation_id: The per-turn invocation UUID (correlates with evidence).
        base_model_settings: Assembly-point runtime settings used as the
            merge base (``None`` preserves the pre-6d behavior).

    Returns:
        A kwargs dict (``usage_limits`` / ``model_settings``) for
        ``agent.run_stream()``.
    """
    if resolver is None:
        if base_model_settings:
            return {"model_settings": dict(base_model_settings)}
        return {}
    resolved = resolver.resolve(
        config=config,
        budget=None,
        invocation_id=invocation_id,
    )
    kwargs: dict[str, object] = {}
    if resolved.usage_limits is not None:
        kwargs["usage_limits"] = resolved.usage_limits
    merged = merge_model_settings(base_model_settings, resolved)
    if merged is not None:
        kwargs["model_settings"] = merged
    return kwargs
