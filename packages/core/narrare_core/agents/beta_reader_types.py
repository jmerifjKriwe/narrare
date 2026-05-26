"""Output types for BetaReaderAgent.

Two output modes:
  - Phase 1 (Full Analysis): Broad feedback across all categories
  - Phase 2 (Deep Dive): Focused analysis on one category

Follows the same pattern as worldbuilding_types.py.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Phase 1: Full Chapter Analysis
# ---------------------------------------------------------------------------


class AgentFeedbackItem(BaseModel):
    """A single feedback item from the agent's raw output.

    The service layer maps this to the public BetaFeedbackItem.
    """

    category: str  # plot, character, prose, pacing, experience
    severity: str  # critical, moderate, minor
    location: str | None = None
    title: str
    description: str
    suggestion: str | None = None
    text_excerpt: str | None = None


class AgentStrength(BaseModel):
    """A strength identified by the agent."""

    category: str
    title: str
    description: str
    text_excerpt: str | None = None


class AgentReaderQuestion(BaseModel):
    """A question a reader would ask."""

    category: str
    location: str | None = None
    question: str
    context: str | None = None


class AgentOverallAssessment(BaseModel):
    """Overall assessment scores."""

    summary: str
    reader_engagement: int = Field(ge=1, le=10)
    emotional_impact: int = Field(ge=1, le=10)
    pacing_score: int = Field(ge=1, le=10)
    prose_quality: int = Field(ge=1, le=10)
    plot_progression: int = Field(ge=1, le=10)
    character_development: int = Field(ge=1, le=10)


class BetaReaderPhase1Output(BaseModel):
    """Agent output for Phase 1 (full chapter analysis)."""

    strengths: list[AgentStrength]
    feedback: list[AgentFeedbackItem]
    questions: list[AgentReaderQuestion]
    overall: AgentOverallAssessment


# ---------------------------------------------------------------------------
# Phase 2: Category Deep Dive
# ---------------------------------------------------------------------------


class AgentDeepDiveFeedback(BaseModel):
    """Detailed feedback item for a specific category."""

    category: str
    severity: str
    location: str | None = None
    title: str
    description: str
    suggestion: str | None = None
    text_excerpt: str | None = None


class BetaReaderPhase2Output(BaseModel):
    """Agent output for Phase 2 (category deep dive)."""

    detailed_feedback: list[AgentDeepDiveFeedback]
    revision_suggestions: list[str]
    category_score: int = Field(ge=1, le=10)


# ---------------------------------------------------------------------------
# Agent Dependencies
# ---------------------------------------------------------------------------


class BetaReaderDeps(BaseModel):
    """Dependencies for BetaReaderAgent.

    Attributes:
        language: Output language code.
        chapter_text: The full text of the chapter(s) being analyzed.
        chapter_titles: Titles of the chapters (for context).
        word_count: Total word count of the analyzed text.
        previous_chapter_summaries: Summaries of chapters before the analyzed ones.
        kb_characters: Relevant character entries from the KB.
        kb_locations: Relevant location entries from the KB.
        genre: The project's genre (if specified).
        focus_categories: Categories to focus on (None = all).
        deepdive_category: Category for Phase 2 deep-dive.
        phase1_strengths_summary: Summary of Phase 1 strengths for Phase 2.
        phase1_feedback_summary: Summary of Phase 1 feedback for Phase 2.
    """

    language: str = "en"
    chapter_text: str = ""
    chapter_titles: list[str] = Field(default_factory=list)
    word_count: int = 0
    previous_chapter_summaries: list[str] = Field(default_factory=list)
    kb_characters: list[dict[str, str]] = Field(default_factory=lambda: [])
    kb_locations: list[dict[str, str]] = Field(default_factory=lambda: [])
    genre: str = ""
    focus_categories: list[str] | None = None
    # Phase 2 only:
    deepdive_category: str | None = None
    phase1_strengths_summary: str | None = None
    phase1_feedback_summary: str | None = None
