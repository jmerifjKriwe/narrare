"""AI-powered structure remap using chapter summaries.

Uses chapter summary text to classify each chapter's narrative role
within a given story structure. Falls back to position-ratio heuristic
when insufficient summaries exist.

Invocation pipeline (ADR-048): ``analyze_chapter_role()`` accepts an
optional ``invocation_pipeline`` and composes its prompt through the
governed EXTRACT/remap route (Mode 1 — composer-driven). The remap
template (``analysis/en/remap/system.md``) is resolved, validated, and
versioned by PromptRegistry/PromptComposer; the composed system prompt
is passed to ``agent.run()`` as the runtime prompt. When
``invocation_pipeline`` is ``None`` (backward-compatible default), the
prompt is composed directly via ``composer.build()`` without pipeline
evidence.

Prepared triple (19009e17 kwargs pass-through): ``analyze_chapter_role()``
also accepts ``model_settings`` / ``usage_limits`` and forwards them to
``agent.run()`` so the ``ModelRegistry.prepare()`` triple crosses this
boundary in full.

See ADR-015 Phase 5 — Storyboard AI Enhancement.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.ai_invocation import (
    PromptInvocationContext,
    compose_invocation,
)
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits

    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.prompts.composer import PromptComposer

logger = logging.getLogger(__name__)
_remap_structlog = structlog.get_logger(__name__)


async def _compose_remap_system_prompt(
    composer: PromptComposer,
    invocation_pipeline: InvocationPipeline | None,
    structure_type: str,
    summary: str,
) -> str | None:
    """Compose the remap prompt via the governed EXTRACT/remap route.

    Mode 1 (composer-driven, ADR-048): when an ``invocation_pipeline``
    is wired, ``compose_invocation()`` merges pipeline enrichment into
    the context, composes the real prompt, and records invocation
    evidence in one step. On pipeline failure it falls back to a direct
    ``composer.build()`` (evidence-less but still governed). A total
    composition failure returns ``None`` so the caller degrades to the
    position-ratio heuristic (RULE-11: logged, never silent).

    Args:
        composer: The injected PromptComposer (governed route owner).
        invocation_pipeline: Optional pipeline for enrichment + evidence.
        structure_type: The story structure type.
        summary: The chapter summary text.

    Returns:
        The composed system prompt, or ``None`` when composition failed.
    """
    context = PromptContext(
        language="en",
        mode="remap",
        extra={"structure_type": structure_type, "summary": summary},
    )
    if invocation_pipeline is not None:
        try:
            result = await compose_invocation(
                invocation_pipeline=invocation_pipeline,
                invocation_context=PromptInvocationContext(
                    feature_id="planning_remap",
                    intent=LLMIntent.EXTRACT,
                    language="en",
                ),
                composer=composer,
                prompt_context=context,
                intent=LLMIntent.EXTRACT,
            )
            assert result.composed_prompt is not None  # Mode 1 always composes
            return result.composed_prompt.system
        except Exception:
            _remap_structlog.warning(
                "remap_invocation_compose_failed",
                feature_id="planning_remap",
            )
    try:
        return (await composer.build(LLMIntent.EXTRACT, context)).system
    except Exception:
        _remap_structlog.warning(
            "remap_prompt_compose_failed",
            feature_id="planning_remap",
        )
        return None


class AIRemapService:
    """Analyzes chapter summaries to suggest story structure stages.

    Uses chapter summary text to classify each chapter's narrative role
    within a given story structure. Falls back to position-ratio heuristic
    when insufficient summaries exist.
    """

    DEFAULT_COVERAGE_THRESHOLD = 0.5  # 50%

    def __init__(self, composer: PromptComposer) -> None:
        """Initialize the service with its governed prompt composer.

        Args:
            composer: PromptComposer used to build the remap prompt via
                the EXTRACT/remap route (RULE-02: no raw template loads).
        """
        self._composer = composer

    async def analyze_chapter_role(
        self,
        summary: str,
        structure_type: str,
        agent: Any | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        *,
        model_settings: ModelSettings | None = None,
        usage_limits: UsageLimits | None = None,
    ) -> str:
        """Analyze a chapter summary to determine its likely stage.

        Args:
            summary: The chapter summary text.
            structure_type: The story structure type (e.g. "three_act").
            agent: Optional ChapterSummaryAgent instance for AI analysis.
            invocation_pipeline: Optional InvocationPipeline for enrichment
                and evidence recording (ADR-048 Mode 1). When ``None``,
                the prompt is composed directly without pipeline evidence
                (backward-compatible default).
            model_settings: Settings half of the ``ModelRegistry.prepare()``
                triple — forwarded to the agent run (kwargs pass-through,
                19009e17 convention). ``None`` when no settings apply.
            usage_limits: Usage limits from the prepared triple —
                forwarded to the agent run. ``None`` when the caller
                provided none.

        Returns:
            A stage ID string (e.g. "act-1", "act-2").
        """
        if not summary.strip():
            return ""

        if agent is None:
            return ""

        # Compose the prompt via the governed EXTRACT/remap route
        # (RULE-02). Composition failure degrades to "" so the caller
        # falls back to the position heuristic (RULE-11).
        prompt = await _compose_remap_system_prompt(
            self._composer, invocation_pipeline, structure_type, summary
        )
        if prompt is None:
            return ""

        deps_type = type("Deps", (), {"language": "en"})()
        try:
            # narrare: allow-agent reason="injected agent, not instantiated here"
            result = await agent.run(
                prompt=prompt,
                deps=deps_type,
                model_settings=model_settings,
                usage_limits=usage_limits,
            )
            stage = result.summary.strip().lower()
            if stage:
                return stage
        except Exception as exc:
            logger.warning("analyze_chapter_role_failed", exc_info=exc)

        return ""

    def meets_coverage_threshold(
        self,
        total_chapters: int,
        chapters_with_summaries: int,
        threshold: float | None = None,
    ) -> bool:
        """Check if enough chapters have summaries for AI remap.

        Args:
            total_chapters: Total number of chapters.
            chapters_with_summaries: Number of chapters with non-empty summaries.
            threshold: Coverage ratio threshold (default 0.5).

        Returns:
            True if coverage meets or exceeds threshold.
        """
        if total_chapters == 0:
            return False
        thresh = threshold or self.DEFAULT_COVERAGE_THRESHOLD
        return (chapters_with_summaries / total_chapters) >= thresh

    def calculate_confidence(
        self,
        total_chapters: int,
        chapters_with_summaries: int,
    ) -> float:
        """Calculate AI confidence based on summary coverage ratio.

        Returns:
            0.0 if no summaries, 0.5 if partial, 1.0 if full coverage.
        """
        if total_chapters == 0:
            return 0.0
        ratio = chapters_with_summaries / total_chapters
        if ratio >= 1.0:
            return 1.0
        if ratio >= self.DEFAULT_COVERAGE_THRESHOLD:
            return 0.5
        return 0.0
