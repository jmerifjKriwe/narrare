"""Writing module dependency injection — shared pipeline factory.

Provides the ``_create_pipeline`` helper used by all pipeline-based
writing service factories to avoid duplicating WritingPipeline
construction (RULE-04 compliance).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import (
    get_agent_registry,
    get_composer,
    get_invocation_pipeline,
    get_model_registry,
)

if TYPE_CHECKING:
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline


def create_pipeline(
    draft_processor: DraftProcessor,
    tier_overrides: dict[str, float] | None = None,
) -> WritingPipeline:
    """Create a WritingPipeline with the invocation pipeline wired.

    Shared helper used by all writing service factories to avoid
    duplicating the WritingPipeline construction (RULE-04 compliance).

    Args:
        draft_processor: Shared DraftProcessor instance (also passed to
            the service for direct use).
        tier_overrides: Optional per-tier percentage overrides forwarded
            verbatim to :class:`WritingContextAssembler` (and on to
            :class:`TokenBudgetManager`).  ``None`` (default) preserves the
            mode-specific allocations (extend / rewrite / first-chapter).
            Production factories source this from the resolved
            ``TokenLimitsService.get_resolved_limits().tier_percentages``
            (FIND-012 / CR-AUFG-08-02).

    Returns:
        Configured WritingPipeline with InvocationPipeline attached.
    """
    from narrare.writing.voice_profile_adapter import make_voice_profile_consumer
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.pipeline import WritingPipeline

    return WritingPipeline(
        registry=get_model_registry(),
        composer=get_composer(),
        context_assembler=WritingContextAssembler(tier_overrides=tier_overrides),
        draft_processor=draft_processor,
        agent_registry=get_agent_registry(),
        invocation_pipeline=get_invocation_pipeline(),
        voice_profile_consumer_factory=make_voice_profile_consumer,
    )
