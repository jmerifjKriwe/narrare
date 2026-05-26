"""AI-powered structure remap using chapter summaries.

Uses chapter summary text to classify each chapter's narrative role
within a given story structure. Falls back to position-ratio heuristic
when insufficient summaries exist.

See ADR-015 Phase 5 — Storyboard AI Enhancement.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Load bundled remap prompt template (loaded once at module level)
_remap_prompt_template: str | None = None


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
    ) -> str:
        """Analyze a chapter summary to determine its likely stage.

        Args:
            summary: The chapter summary text.
            structure_type: The story structure type (e.g. "three_act").
            agent: Optional ChapterSummaryAgent instance for AI analysis.

        Returns:
            A stage ID string (e.g. "act-1", "act-2").
        """
        if not summary.strip():
            return ""

        if agent is not None:
            # Load prompt from bundled template (RULE-02: prompts in core/prompts/)
            prompt_template = _get_remap_prompt()
            prompt = prompt_template.replace("{{structure_type}}", structure_type).replace(
                "{{summary}}", summary
            )
            deps_type = type("Deps", (), {"language": "en"})()
            try:
                # narrare: allow-agent reason="injected agent, not instantiated here"
                result = await agent.run(prompt=prompt, deps=deps_type)  # type: ignore[union-attr]
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
