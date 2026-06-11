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


def create_pipeline(draft_processor: DraftProcessor) -> WritingPipeline:
    """Create a WritingPipeline with the invocation pipeline wired.

    Shared helper used by all writing service factories to avoid
    duplicating the WritingPipeline construction (RULE-04 compliance).

    Args:
        draft_processor: Shared DraftProcessor instance (also passed to
            the service for direct use).

    Returns:
        Configured WritingPipeline with InvocationPipeline attached.
    """
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.pipeline import WritingPipeline

    return WritingPipeline(
        registry=get_model_registry(),
        composer=get_composer(),
        context_assembler=WritingContextAssembler(),
        draft_processor=draft_processor,
        agent_registry=get_agent_registry(),
        invocation_pipeline=get_invocation_pipeline(),
    )
