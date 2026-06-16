"""Invocation composition helpers for WikiService (ADR-048 Mode 2).

Wiki agents compose their own prompts internally (``WikiPromptLoader``),
so ``compose_wiki_invocation()`` uses a ``ManualInjectionDeclaration`` per
ADR-048 Mode 2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.ai_invocation import (
    PromptInvocationContext,
    compose_invocation,
)
from narrare_core.wiki.manual_injection import (
    WIKI_CHAPTER_GENERATION_MANUAL_INJECTION,
    WIKI_ENTITY_GENERATION_MANUAL_INJECTION,
)

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.intents import LLMIntent

logger = structlog.get_logger(__name__)


async def compose_wiki_invocation(
    invocation_pipeline: InvocationPipeline | None,
    feature_id: str,
    intent: LLMIntent,
    project_id: str | None = None,
) -> None:
    """Run ``compose_invocation()`` with Mode 2 for wiki agent calls.

    When ``invocation_pipeline`` is ``None`` (backward-compatible default),
    the pipeline is gracefully skipped — no evidence, no enrichment.

    Failures are logged and swallowed — the agent call proceeds regardless
    (RULE-11 graceful degradation).

    Args:
        invocation_pipeline: The invocation pipeline, or None to skip.
        feature_id: Feature identifier (e.g. ``"wiki_generate_entity"``).
        intent: The LLM intent for the invocation.
        project_id: Optional project/novel identifier.
    """
    if invocation_pipeline is None:
        return

    ctx = PromptInvocationContext(
        feature_id=feature_id,
        intent=intent,
        project_id=project_id,
        language="en",
    )
    manual_injection = (
        WIKI_ENTITY_GENERATION_MANUAL_INJECTION
        if feature_id == "wiki_generate_entity"
        else WIKI_CHAPTER_GENERATION_MANUAL_INJECTION
    )
    try:
        await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=ctx,
            manual_injection=manual_injection,
        )
    except Exception:
        logger.warning(
            "wiki_invocation_composition_failed",
            feature_id=feature_id,
            exc_info=True,
        )
