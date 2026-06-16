"""AI-powered structure remap using chapter summaries.

Uses chapter summary text to classify each chapter's narrative role
within a given story structure. Falls back to position-ratio heuristic
when insufficient summaries exist.

Invocation pipeline (ADR-048): ``analyze_chapter_role()`` accepts an
optional ``invocation_pipeline`` and calls ``compose_invocation()`` with
Mode 2 (agent-internal composition) because ``ChapterSummaryAgent``
composes its prompt internally from the summary and structure type.
When ``invocation_pipeline`` is ``None`` (backward-compatible default),
the pipeline is gracefully skipped.

See ADR-015 Phase 5 — Storyboard AI Enhancement.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.ai_invocation import (
    ManualInjectionDeclaration,
    PromptInvocationContext,
    compose_invocation,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

logger = logging.getLogger(__name__)
_remap_structlog = structlog.get_logger(__name__)

# Load bundled remap prompt template (loaded once at module level)
_remap_prompt_template: str | None = None

# Manual-injection declaration for Mode 2 (agent-internal composition).
# ChapterSummaryAgent composes its prompt internally from the summary and
# structure type — the service delegates to agent.run() with a rendered
# prompt template.
_REMAP_MANUAL_INJECTION = ManualInjectionDeclaration(
    reason=(
        "ChapterSummaryAgent receives a rendered prompt template with the "
        "chapter summary and structure type. The agent internally processes "
        "this prompt and returns a stage classification. No PromptComposer "
        "is used at the service level."
    ),
    variables=("summary", "structure_type"),
    injection_mechanism="agent_deps",
    precedence_level="generated_suggestion",
)


def _get_remap_prompt() -> str:
    """Load the bundled remap prompt template (lazy, cached)."""
    global _remap_prompt_template
    if _remap_prompt_template is None:
        path = (
            Path(__file__).parent.parent
            / "prompts"
            / "_bundled"
            / "analysis"
            / "en"
            / "remap"
            / "system.md"
        )
        _remap_prompt_template = path.read_text(encoding="utf-8")
    return _remap_prompt_template


async def _compose_remap_invocation(
    invocation_pipeline: InvocationPipeline,
    structure_type: str,
    summary: str,
) -> None:
    """Compose a remap invocation via the pipeline (Mode 2).

    Called before ``agent.run()`` to record evidence that a remap
    classification was requested. Uses ``compose_invocation()`` with a
    ``ManualInjectionDeclaration`` because ``ChapterSummaryAgent``
    composes its prompt internally.

    Args:
        invocation_pipeline: The invocation pipeline.
        structure_type: The story structure type.
        summary: The chapter summary text.

    Raises:
        Any exceptions are logged and swallowed — remap proceeds
        without pipeline evidence on failure.
    """
    ctx = PromptInvocationContext(
        feature_id="planning_remap",
        intent=LLMIntent.PLAN,
        language="en",
    )
    try:
        await compose_invocation(
            invocation_pipeline=invocation_pipeline,
            invocation_context=ctx,
            manual_injection=_REMAP_MANUAL_INJECTION,
        )
    except Exception:
        _remap_structlog.warning(
            "remap_invocation_compose_failed",
            feature_id="planning_remap",
        )


class AIRemapService:
    """Analyzes chapter summaries to suggest story structure stages.

    Uses chapter summary text to classify each chapter's narrative role
    within a given story structure. Falls back to position-ratio heuristic
    when insufficient summaries exist.
    """

    DEFAULT_COVERAGE_THRESHOLD = 0.5  # 50%

    async def analyze_chapter_role(
        self,
        summary: str,
        structure_type: str,
        agent: Any | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> str:
        """Analyze a chapter summary to determine its likely stage.

        Args:
            summary: The chapter summary text.
            structure_type: The story structure type (e.g. "three_act").
            agent: Optional ChapterSummaryAgent instance for AI analysis.
            invocation_pipeline: Optional InvocationPipeline for evidence
                recording (ADR-048). When ``None``, pipeline is skipped
                (backward-compatible default).

        Returns:
            A stage ID string (e.g. "act-1", "act-2").
        """
        if not summary.strip():
            return ""

        if agent is not None:
            # Record invocation evidence via pipeline (ADR-048 Mode 2).
            # ChapterSummaryAgent composes its prompt internally, so we use
            # a manual-injection declaration. Failures are logged and
            # swallowed — generation proceeds regardless (RULE-11).
            if invocation_pipeline is not None:
                await _compose_remap_invocation(invocation_pipeline, structure_type, summary)

            # Load prompt from bundled template (RULE-02: prompts in core/prompts/)
            prompt_template = _get_remap_prompt()
            prompt = prompt_template.replace("{{structure_type}}", structure_type).replace(
                "{{summary}}", summary
            )
            deps_type = type("Deps", (), {"language": "en"})()
            try:
                # narrare: allow-agent reason="injected agent, not instantiated here"
                result = await agent.run(prompt=prompt, deps=deps_type)
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
