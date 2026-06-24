"""Shared invocation context builder for non-writing services.

Provides :func:`build_invocation_context` — a lightweight helper for
analysis, KB, and planning services that need to create
:class:`PromptInvocationContext` instances for the
:class:`InvocationPipeline` and :func:`compose_invocation`.

This module is the non-writing counterpart to
``narrare_core.writing._invocation_adapter``. That adapter wraps
``PromptComposer.build()`` with prepare/finalize. This one provides a
simpler API for services that call agents directly (not through
``WritingPipeline``).

History:
    The deprecated ``record_invocation_evidence()`` and
    ``safe_record_evidence()`` functions were removed in ADR-048 Slice F
    (Phase 3 cleanup). The former fire-and-forget compose wrapper was
    removed after all callers migrated to direct :func:`compose_invocation`
    calls (ADR-048 Q1 follow-up): it discarded the composed result
    (RULE-20) and masked the real Mode 2 contract behind a single-
    responsibility-violating convenience function (RULE-06). Services now
    call :func:`compose_invocation` explicitly with ``manual_injection=``
    (Mode 2) or ``composer=`` (Mode 1).

See:
    ADR-040, ADR-048, INFRA-013, CONSTRAINTS.md RULE-03/RULE-06/RULE-20.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.ai_invocation.models import PromptInvocationContext
    from narrare_core.llm.intents import LLMIntent


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
        A :class:`PromptInvocationContext` ready for ``compose_invocation``.
    """
    from narrare_core.ai_invocation.models import PromptInvocationContext

    return PromptInvocationContext(
        feature_id=feature_id,
        intent=intent,
        user_id=user_id,
        project_id=project_id,
        language=language,
    )
