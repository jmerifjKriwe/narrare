"""Shared invocation context builders for non-writing services.

Provides :func:`build_invocation_context` and
:func:`safe_compose_invocation` — lightweight helpers for analysis and
KB services that need to create :class:`PromptInvocationContext` instances
for the :class:`InvocationPipeline` and compose invocations through it.

This module is the non-writing counterpart to
``narrare_core.writing._invocation_adapter``. That adapter wraps
``PromptComposer.build()`` with prepare/finalize. This one provides a
simpler API for services that call agents directly (not through
``WritingPipeline``).

The deprecated ``record_invocation_evidence()`` and
``safe_record_evidence()`` functions were removed in ADR-048 Slice F
(Phase 3 cleanup). Use :func:`safe_compose_invocation` instead, which
correlates evidence with the real composed prompt via
:func:`compose_invocation`.

See:
    ADR-040, ADR-048, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from narrare_core.ai_invocation.manual_injection import ManualInjectionDeclaration
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
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


async def safe_compose_invocation(
    pipeline: InvocationPipeline | None,
    *,
    feature_id: str,
    intent: LLMIntent,
    user_id: object | None = None,
    project_id: object | None = None,
    language: str = "en",
    manual_injection: ManualInjectionDeclaration,
) -> None:
    """Compose invocation (Mode 2) for evidence recording. Silently no-ops when pipeline is None.

    Non-deprecated replacement for safe_record_evidence() per ADR-048.
    Uses compose_invocation() with ManualInjectionDeclaration (Mode 2 -- agent-internal).

    Failures are logged and swallowed -- the service proceeds with the agent call
    regardless of evidence recording issues.
    """
    if pipeline is None:
        return

    from narrare_core.ai_invocation import compose_invocation

    context = build_invocation_context(
        feature_id=feature_id,
        intent=intent,
        user_id=user_id,
        project_id=project_id,
        language=language,
    )
    try:
        await compose_invocation(
            invocation_pipeline=pipeline,
            invocation_context=context,
            manual_injection=manual_injection,
        )
    except Exception:
        logger.warning(
            "invocation_composition_failed",
            feature_id=feature_id,
            exc_info=True,
        )
