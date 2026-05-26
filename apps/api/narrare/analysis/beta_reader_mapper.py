"""Response mapping for beta reader analysis.

Maps agent output types (Phase 1 / Phase 2) to public API response models.
Extracted from beta_reader_service.py to keep service under 300 lines (RULE-04).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from narrare.analysis.beta_reader_cache import BetaReaderCache
from narrare.analysis.contracts import FeedbackCategory, FeedbackSeverity
from narrare.analysis.schemas import (
    BetaFeedbackItem,
    BetaReaderDeepDiveResponse,
    BetaReaderOverallAssessment,
    BetaReaderQuestion,
    BetaReaderResponse,
    BetaReaderStrength,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.agents.beta_reader_types import (
        BetaReaderDeps,
        BetaReaderPhase1Output,
        BetaReaderPhase2Output,
    )


def map_phase1_response(
    output: BetaReaderPhase1Output,
    novel_id: UUID,
    chapter_ids: list[str],
    word_count: int,
) -> BetaReaderResponse:
    """Map agent Phase 1 output to public BetaReaderResponse.

    Args:
        output: Agent Phase 1 structured output.
        novel_id: The novel UUID.
        chapter_ids: The analyzed chapter IDs.
        word_count: Total word count.

    Returns:
        Public BetaReaderResponse ready for caching and HTTP response.
    """
    strengths = [
        BetaReaderStrength(
            category=FeedbackCategory(s.category),
            title=s.title,
            description=s.description,
            text_excerpt=s.text_excerpt,
        )
        for s in output.strengths
    ]

    feedback = [
        BetaFeedbackItem(
            category=FeedbackCategory(f.category),
            severity=FeedbackSeverity(f.severity),
            location=f.location,
            title=f.title,
            description=f.description,
            suggestion=f.suggestion,
            text_excerpt=f.text_excerpt,
        )
        for f in output.feedback
    ]

    questions = [
        BetaReaderQuestion(
            category=FeedbackCategory(q.category),
            location=q.location,
            question=q.question,
            context=q.context,
        )
        for q in output.questions
    ]

    overall = BetaReaderOverallAssessment(
        summary=output.overall.summary,
        reader_engagement=output.overall.reader_engagement,
        emotional_impact=output.overall.emotional_impact,
        pacing_score=output.overall.pacing_score,
        prose_quality=output.overall.prose_quality,
        plot_progression=output.overall.plot_progression,
        character_development=output.overall.character_development,
    )

    cache_key = BetaReaderCache.hash_chapter_ids(chapter_ids)

    return BetaReaderResponse(
        novel_id=str(novel_id),
        chapter_ids=chapter_ids,
        total_word_count=word_count,
        strengths=strengths,
        feedback=feedback,
        questions=questions,
        overall=overall,
        analyzed_at=datetime.now(tz=UTC).isoformat(),
        cache_key=cache_key,
    )


def map_phase2_response(
    output: BetaReaderPhase2Output,
    novel_id: UUID,
    category: FeedbackCategory,
) -> BetaReaderDeepDiveResponse:
    """Map agent Phase 2 output to public BetaReaderDeepDiveResponse.

    Args:
        output: Agent Phase 2 structured output.
        novel_id: The novel UUID.
        category: The deep-dived category.

    Returns:
        Public BetaReaderDeepDiveResponse ready for HTTP response.
    """
    detailed_feedback = [
        BetaFeedbackItem(
            category=FeedbackCategory(f.category),
            severity=FeedbackSeverity(f.severity),
            location=f.location,
            title=f.title,
            description=f.description,
            suggestion=f.suggestion,
            text_excerpt=f.text_excerpt,
        )
        for f in output.detailed_feedback
    ]

    return BetaReaderDeepDiveResponse(
        novel_id=str(novel_id),
        category=category,
        detailed_feedback=detailed_feedback,
        revision_suggestions=output.revision_suggestions,
        category_score=output.category_score,
        analyzed_at=datetime.now(tz=UTC).isoformat(),
    )


def build_user_prompt(deps: BetaReaderDeps) -> str:
    """Build user prompt from BetaReaderDeps for Phase 1.

    Formats the chapter text and context into a user-facing prompt.
    Does NOT build the system prompt (PromptComposer handles that).

    Args:
        deps: Fully populated BetaReaderDeps.

    Returns:
        User prompt string for agent.run_phase1().
    """
    parts: list[str] = []

    if deps.genre:
        parts.append(f"Genre: {deps.genre}")

    parts.append(f"Chapters: {', '.join(deps.chapter_titles)}")
    parts.append(f"Word count: {deps.word_count}")

    if deps.focus_categories:
        parts.append(f"Focus categories: {', '.join(deps.focus_categories)}")

    if deps.previous_chapter_summaries:
        parts.append("\n## Previous Chapter Summaries")
        for i, summary in enumerate(deps.previous_chapter_summaries, 1):
            parts.append(f"Chapter {i}: {summary}")

    if deps.kb_characters:
        parts.append("\n## Characters")
        for char in deps.kb_characters:
            parts.append(f"- {char['name']}: {char.get('summary', '')}")

    if deps.kb_locations:
        parts.append("\n## Locations")
        for loc in deps.kb_locations:
            parts.append(f"- {loc['name']}: {loc.get('summary', '')}")

    parts.append("\n## Chapter Text")
    parts.append(deps.chapter_text)

    parts.append("\nAnalyze this chapter as a beta reader.")

    return "\n".join(parts)


def build_deepdive_prompt(deps: BetaReaderDeps) -> str:
    """Build user prompt for Phase 2 deep-dive.

    Args:
        deps: BetaReaderDeps with deepdive_category set.

    Returns:
        User prompt string for agent.run_phase2().
    """
    parts: list[str] = []

    parts.append(f"Deep-dive analysis on: {deps.deepdive_category}")

    if deps.phase1_strengths_summary:
        parts.append(f"\nPhase 1 strengths: {deps.phase1_strengths_summary}")

    if deps.phase1_feedback_summary:
        parts.append(f"Phase 1 issues: {deps.phase1_feedback_summary}")

    parts.append("\n## Chapter Text")
    parts.append(deps.chapter_text)

    parts.append(
        f"\nProvide a detailed deep-dive on {deps.deepdive_category} "
        f"with specific text references and revision suggestions."
    )

    return "\n".join(parts)
