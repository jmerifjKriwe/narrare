"""Shared invocation context builders for non-writing services.

Provides :func:`build_invocation_context` and
:func:`record_invocation_evidence` — lightweight helpers for analysis and
KB services that need to create :class:`PromptInvocationContext` instances
for the :class:`InvocationPipeline`.

This module is the non-writing counterpart to
``narrare_core.writing._invocation_adapter``. That adapter wraps
``PromptComposer.build()`` with prepare/finalize. This one provides a
simpler API for services that call agents directly (not through
``WritingPipeline``).

See:
    ADR-040, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.pipeline import (
        FinalizedInvocation,
        InvocationPipeline,
        PreparedInvocation,
    )
    from narrare_core.llm.intents import LLMIntent

logger = structlog.get_logger(__name__)


def build_invocation_context(
    *,
    feature_id: str,
    intent: LLMIntent,
    user_id: object | None = None,
    project_id: object | None = None,
    language: str = "en",
) -> PromptInvocationContext:
    """Create a :class:`PromptInvocationContext` for an analysis or KB operation.

    This is the standard entry point for wiring invocation evidence into
    services that call agents directly (not through ``WritingPipeline``).

    Args:
        feature_id: Domain-specific feature identifier. Convention:
            ``{domain}_{operation}`` e.g. ``"analysis_beta_read"``,
            ``"kb_extract"``, ``"kb_consistency"``.
        intent: The LLM intent for this invocation.
        user_id: Optional user identifier for enrichment.
        project_id: Optional project/novel identifier for enrichment.
        language: Language code. Defaults to ``"en"``.

    Returns:
        A :class:`PromptInvocationContext` ready for ``pipeline.prepare()``.
    """
    from narrare_core.ai_invocation.models import PromptInvocationContext

    return PromptInvocationContext(
        feature_id=feature_id,
        intent=intent,
        user_id=user_id,
        project_id=project_id,
        language=language,
    )


async def record_invocation_evidence(
    pipeline: InvocationPipeline,
    context: PromptInvocationContext,
) -> FinalizedInvocation:
    """Run prepare + finalize for a direct agent call.

    Analysis and KB services that call agents directly (not through
    ``WritingPipeline``) should use this function to record invocation
    evidence. It runs both pipeline phases with a placeholder
    :class:`ComposedPrompt` (the evidence record is privacy-safe — it
    never contains raw prompt text).

    Usage::

        async def my_service_method(self, ...):
            ctx = build_invocation_context(
                feature_id="kb_extract",
                intent=LLMIntent.KB_EXTRACT,
                user_id=user_id,
                project_id=novel_id,
            )
            result = await record_invocation_evidence(
                pipeline=self._invocation_pipeline,
                context=ctx,
            )
            # ... run agent ...

    Args:
        pipeline: The :class:`InvocationPipeline` instance.
        context: The invocation context built by :func:`build_invocation_context`.

    Returns:
        A :class:`FinalizedInvocation` with validation and evidence state.
    """
    warnings.warn(
        "record_invocation_evidence() is deprecated per ADR-048 Phase 1: it "
        "finalizes the pipeline with a placeholder prompt and discards "
        "enrichment. Use compose_invocation() instead. This function will be "
        "removed in ADR-048 Phase 3.",
        DeprecationWarning,
        stacklevel=2,
    )
    from narrare_core.prompts.composer import ComposedPrompt

    # Phase 1: prepare (validate + enrich + resolve budget)
    prepared: PreparedInvocation = await pipeline.prepare(context)

    # Phase 2: finalize (validate + record evidence)
    # ComposedPrompt is required by finalize() but evidence is privacy-safe
    # — it never stores raw prompt text. Use placeholder values.
    placeholder_prompt = ComposedPrompt(
        system="[analysis-kb-invocation]",
        user="[direct-agent-call]",
    )
    finalized = await pipeline.finalize(
        placeholder_prompt,
        context,
        prepared=prepared,
    )

    if finalized.evidence_recorded:
        logger.debug(
            "invocation_evidence_recorded",
            feature_id=context.feature_id,
        )

    return finalized


async def safe_record_evidence(
    pipeline: InvocationPipeline | None,
    *,
    feature_id: str,
    intent: LLMIntent,
    user_id: object | None = None,
    project_id: object | None = None,
    language: str = "en",
) -> None:
    """Record invocation evidence; silently no-op when pipeline is ``None``.

    Thin wrapper used by analysis and KB services to avoid duplicating the
    null-check / try-except / logging boilerplate in every ``_record_evidence``
    method (ADR-040, RULE-04).
    """
    warnings.warn(
        "safe_record_evidence() is deprecated per ADR-048 Phase 1: it records "
        "placeholder evidence with discarded enrichment. Use "
        "compose_invocation() instead. This function will be removed in "
        "ADR-048 Phase 3.",
        DeprecationWarning,
        stacklevel=2,
    )
    if pipeline is None:
        return

    try:
        ctx = build_invocation_context(
            feature_id=feature_id,
            intent=intent,
            user_id=user_id,
            project_id=project_id,
            language=language,
        )
        await record_invocation_evidence(pipeline, ctx)
    except Exception:
        logger.warning(
            "invocation_evidence_recording_failed",
            feature_id=feature_id,
            exc_info=True,
        )
