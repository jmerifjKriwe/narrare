"""Band-summary prompt composition + run-prompt formatting (RULE-02b).

Extracted from ``band_summary_service.py`` for RULE-04 compliance (the
service sat at its 300-line hard limit after the Task 6d prepare()
migration). Owns the single responsibility of turning runtime inputs
into the governed ``band_summary`` system prompt and the user-channel
run prompt — mirroring the ``series_consistency_prompt.py`` /
``series_consistency_runtime_content.py`` split of the sibling
series-consistency feature.

See:
    RULE-02/02b (PromptComposer cascade, no inline prompt building),
    RULE-04 (Modularise, never compress),
    RULE-06 (One responsibility per file).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.ai_invocation import compose_invocation
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)

#: Composer mode key for the governed band_summary prompt (RULE-02b).
_BAND_SUMMARY_MODE = "band_summary"


async def compose_band_summary_system_prompt(
    *,
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    novel_title: str,
    genre: str,
    language: str,
    novel_id: UUID,
) -> str:
    """Resolve the governed ``band_summary`` system prompt (RULE-02b).

    Uses ``compose_invocation`` (Mode 1, composer-driven) with the
    InvocationPipeline when available, falling back to direct
    ``composer.build`` on any failure — mirroring ``ChapterSummaryService``
    so a pipeline hiccup never blocks generation.
    """
    from narrare._app.invocation_context import build_invocation_context

    context = PromptContext(
        language=language,
        writing_language=language,
        project_title=novel_title,
        genre=genre,
        mode=_BAND_SUMMARY_MODE,
    )
    invocation_context = build_invocation_context(
        feature_id="series_band_summary",
        intent=LLMIntent.SUMMARIZE,
        project_id=novel_id,
        language=language,
    )
    try:
        invocation_result = await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=invocation_context,
            composer=composer,
            prompt_context=context,
            intent=LLMIntent.SUMMARIZE,
        )
        assert invocation_result.composed_prompt is not None  # Mode 1 always composes
        return invocation_result.composed_prompt.system
    except Exception:
        logger.warning(
            "band_summary_composition_failed",
            feature_id="series_band_summary",
            exc_info=True,
        )
        composed = await composer.build(LLMIntent.SUMMARIZE, context)
        return composed.system


def format_chapter_summaries(chapter_summaries: list[str]) -> str:
    """Format chapter summaries as the agent run prompt (user-channel runtime content).

    Numbered, one per line — mirrors how analysis agents receive their passage.
    Business-logic formatting detail owned by this prompt module (RULE-06).
    """
    return "\n".join(f"{i}. {s}" for i, s in enumerate(chapter_summaries, start=1))
