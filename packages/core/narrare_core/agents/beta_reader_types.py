"""Output types for BetaReaderAgent.

Two output modes:
  - Phase 1 (Full Analysis): Broad feedback across all categories
  - Phase 2 (Deep Dive): Focused analysis on one category

Follows the same pattern as worldbuilding_types.py.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

#: Severity vocabulary for beta-reader feedback — mirrors the public
#: ``FeedbackSeverity`` contract (``narrare.analysis.contracts``) by value;
#: core must not import the API-layer enum. Pinning the Literal makes
#: pydantic-ai retry translated/invalid severities (e.g. German "mittel",
#: eval run 2026-09-14-168945f4-1) instead of shipping them.
type BetaSeverity = Literal["critical", "moderate", "minor"]

#: Revision-suggestion count contract (deepdive template Quality Rules;
#: eval instrument spec 2026-09-14 §5). Enforced by a field_validator on
#: :class:`BetaReaderPhase2Output`.
MIN_REVISION_SUGGESTIONS: int = 3
MAX_REVISION_SUGGESTIONS: int = 6

# ---------------------------------------------------------------------------
# Phase 1: Full Chapter Analysis
# ---------------------------------------------------------------------------


class AgentFeedbackItem(BaseModel):
    """A single feedback item from the agent's raw output.

    The service layer maps this to the public BetaFeedbackItem.
    """

    category: str  # plot, character, prose, pacing, experience
    severity: BetaSeverity
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
    severity: BetaSeverity
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

    @field_validator("revision_suggestions")
    @classmethod
    def _enforce_suggestion_count(cls, value: list[str]) -> list[str]:
        """Enforce the 3-6 revision-suggestions contract.

        Raises ValueError (ADR-035 convention) so pydantic wraps it into a
        ValidationError and pydantic-ai retries the output with the contract
        message — out-of-bounds counts (e.g. 8, eval run
        2026-09-14-168945f4-1) never reach services or the eval instrument.
        """
        if not MIN_REVISION_SUGGESTIONS <= len(value) <= MAX_REVISION_SUGGESTIONS:
            raise ValueError(
                f"revision_suggestions must contain "
                f"{MIN_REVISION_SUGGESTIONS} to {MAX_REVISION_SUGGESTIONS} "
                f"suggestions, got {len(value)}"
            )
        return value


# ---------------------------------------------------------------------------
# Agent Dependencies
# ---------------------------------------------------------------------------


class BetaReaderDeps(BaseModel):
    """Dependencies for BetaReaderAgent.

    KB-context fields (``kb_characters`` / ``kb_locations``) carry
    **pre-rendered prompt text** produced by the canonical
    :class:`~narrare.kb.context_contracts.KBContextProvider` (ADR-067) at the
    backend service boundary (ADR-050 envelope, ``.text`` slot). Decision β
    (boundary-rendered text): the agent consumes KB context solely as
    prompt-bound text in its user prompt (``build_budgeted_prompt`` /
    ``build_user_prompt``) — it never inspects these fields structurally, so
    carrying the envelope dataclass shape would be dead weight on the Deps
    and couple the core Deps to the render-contract shape. Provenance flows
    via the provider rendering with ``annotate_provenance=True`` (FIND-017),
    baking inline provenance brackets into the text — identical boundary
    semantics to coreference's ``to_prompt_variables()``. This keeps the
    core Deps a pure text consumer with no KB-envelope dependency (RULE-07).

    Attributes:
        language: Output language code.
        chapter_text: The full text of the chapter(s) being analyzed.
        chapter_titles: Titles of the chapters (for context).
        word_count: Total word count of the analyzed text.
        previous_chapter_summaries: Summaries of chapters before the analyzed ones.
        kb_characters: Pre-rendered KB character context (envelope ``.text``).
            Empty string on empty KB / no provider (RULE-11).
        kb_locations: Pre-rendered KB location context (envelope ``.text``).
            Empty string on empty KB / no provider (RULE-11).
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
    kb_characters: str = ""
    kb_locations: str = ""
    genre: str = ""
    focus_categories: list[str] | None = None
    # Phase 2 only:
    deepdive_category: str | None = None
    phase1_strengths_summary: str | None = None
    phase1_feedback_summary: str | None = None
