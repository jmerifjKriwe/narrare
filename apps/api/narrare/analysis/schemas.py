"""Analysis Pydantic request/response models.

Extracted from contracts.py to keep file sizes under limit (RULE-04).
Contains all Pydantic BaseModel definitions for the analysis module.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003 — Pydantic needs UUID at runtime for validation

from pydantic import BaseModel, Field

from narrare.analysis.contracts import (  # noqa: TC001 — needed at runtime by Pydantic
    FeedbackCategory,
    FeedbackSeverity,
)

# ---------------------------------------------------------------------------
# ANAL-001: Beta Reader — Feedback Types
# ---------------------------------------------------------------------------


class BetaFeedbackItem(BaseModel):
    """A single feedback item from the beta reader.

    Attributes:
        category: Which aspect of writing this feedback addresses.
        severity: How impactful this issue is for readers.
        location: Where in the chapter this applies (paragraph/section reference).
        title: Short summary of the feedback (1-2 sentences).
        description: Detailed explanation of what the issue is.
        suggestion: Concrete actionable suggestion for improvement.
        text_excerpt: The specific text passage this refers to (if applicable).
    """

    category: FeedbackCategory
    severity: FeedbackSeverity
    location: str | None = None
    title: str
    description: str
    suggestion: str | None = None
    text_excerpt: str | None = None


class BetaReaderStrength(BaseModel):
    """A strength identified by the beta reader.

    Attributes:
        category: Which aspect of writing this strength relates to.
        title: Short summary of the strength.
        description: Why this works well.
        text_excerpt: Supporting text passage (if applicable).
    """

    category: FeedbackCategory
    title: str
    description: str
    text_excerpt: str | None = None


class BetaReaderQuestion(BaseModel):
    """A question a reader would ask while reading.

    Attributes:
        category: Which aspect triggered the question.
        location: Where in the chapter this question arises.
        question: The question itself.
        context: Why this question comes up (what triggered it).
    """

    category: FeedbackCategory
    location: str | None = None
    question: str
    context: str | None = None


class BetaReaderOverallAssessment(BaseModel):
    """Overall assessment of the chapter from a reader's perspective.

    Attributes:
        summary: 2-3 sentence overall impression.
        reader_engagement: How engaging the chapter is (1-10).
        emotional_impact: How emotionally resonant (1-10).
        pacing_score: How well-paced the chapter is (1-10).
        prose_quality: Clarity and style quality (1-10).
        plot_progression: How well the plot advances (1-10).
        character_development: How well characters are developed (1-10).
    """

    summary: str
    reader_engagement: int = Field(ge=1, le=10)
    emotional_impact: int = Field(ge=1, le=10)
    pacing_score: int = Field(ge=1, le=10)
    prose_quality: int = Field(ge=1, le=10)
    plot_progression: int = Field(ge=1, le=10)
    character_development: int = Field(ge=1, le=10)


# ---------------------------------------------------------------------------
# ANAL-001: Beta Reader — Request / Response
# ---------------------------------------------------------------------------


class BetaReaderRequest(BaseModel):
    """Request to run a beta reader analysis.

    Attributes:
        chapter_ids: Chapter(s) to analyze. At least one required.
        categories: Filter to specific categories. None = all categories.
        phase: Which phase to run. 'full' = Phase 1 only. 'deepdive' = Phase 2.
        deepdive_category: Required when phase='deepdive'. Which category to deep-dive.
        refresh: If True, bypass cache and force fresh analysis.
    """

    chapter_ids: list[str] = Field(min_length=1, max_length=5)
    categories: list[FeedbackCategory] | None = None
    phase: str = Field(default="full", pattern="^(full|deepdive)$")
    deepdive_category: FeedbackCategory | None = None
    refresh: bool = False


class BetaReaderResponse(BaseModel):
    """Complete beta reader analysis response.

    Attributes:
        novel_id: The project being analyzed.
        chapter_ids: Which chapters were analyzed.
        total_word_count: Total words across analyzed chapters.
        strengths: What works well.
        feedback: Issues and suggestions, organized by category and severity.
        questions: Questions a reader would ask.
        overall: Overall chapter assessment with scores.
        analyzed_at: When the analysis was performed.
        cache_key: Cache key for potential Phase 2 deep-dive reference.
    """

    novel_id: str
    chapter_ids: list[str]
    total_word_count: int
    strengths: list[BetaReaderStrength]
    feedback: list[BetaFeedbackItem]
    questions: list[BetaReaderQuestion]
    overall: BetaReaderOverallAssessment
    analyzed_at: str  # ISO datetime string
    cache_key: str


class BetaReaderDeepDiveRequest(BaseModel):
    """Request for Phase 2 deep-dive analysis.

    Attributes:
        chapter_ids: Same chapters as Phase 1.
        category: Which category to deep-dive.
        cache_key: Cache key from Phase 1 response (for context).
    """

    chapter_ids: list[str] = Field(min_length=1, max_length=5)
    category: FeedbackCategory
    cache_key: str


class BetaReaderDeepDiveResponse(BaseModel):
    """Response from Phase 2 deep-dive analysis.

    Attributes:
        novel_id: The project being analyzed.
        category: The category that was deep-dived.
        detailed_feedback: More granular feedback with text-level references.
        revision_suggestions: Concrete revision suggestions with before/after examples.
        category_score: Detailed score breakdown for this category.
    """

    novel_id: str
    category: FeedbackCategory
    detailed_feedback: list[BetaFeedbackItem]
    revision_suggestions: list[str]
    category_score: int = Field(ge=1, le=10)
    analyzed_at: str


# ---------------------------------------------------------------------------
# ANAL-002: Sentiment Analysis — Request/Response
# ---------------------------------------------------------------------------


class SentimentRequest(BaseModel):
    """Request to analyze chapter sentiment.

    Attributes:
        chapter_ids: One or more chapter UUIDs to analyze.
        language: Optional language override. If omitted, uses novel's
            ``writing_language`` setting.
        detect_arc: Whether to attempt narrative arc detection.
            Defaults to ``True``. Set to ``False`` for short texts.
    """

    chapter_ids: list[UUID]
    language: str | None = None
    detect_arc: bool = True
