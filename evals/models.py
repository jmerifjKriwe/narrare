"""Typed case inputs and outputs for Narrare eval suites."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from evals.models_dialogue_coach import (
    DialogueCoachEvalInput,
    DialogueCoachEvalResult,
    DialogueCoachWeightResult,
)
from evals.models_kb_operations import (
    KBAgentOperationSection,
    KBAssistSection,
    KBImproveSection,
    KBImproveSuggestionSection,
    KBMergeDecisionSection,
    KBMergeSection,
    KBMergeStrategySection,
    KBOperationsInput,
    KBOperationsResult,
)
from evals.models_names import (
    NameGenerationInput,
    NameGenerationResult,
)
from evals.models_planning import (
    CharacterArcPhaseSection,
    CharacterArcSection,
    OutlineSection,
    PlanningStructureInput,
    PlanningStructureResult,
    TimelineEventSection,
    TimelineSection,
    WorldbuildingConnectionSection,
    WorldbuildingGapSection,
    WorldbuildingSection,
)
from evals.models_writing import (
    WritingProseInput,
    WritingProseResult,
)

__all__ = [
    "AnalysisFeedbackInput",
    "AnalysisFeedbackResult",
    "AnalysisMetricsInput",
    "AnalysisMetricsResult",
    "CharacterArcPhaseSection",
    "CharacterArcSection",
    "ChatGenerationInput",
    "ChatGenerationResult",
    "DialogueCoachEvalInput",
    "DialogueCoachEvalResult",
    "DialogueCoachWeightResult",
    "DraftOutputField",
    "KBAgentOperationSection",
    "KBAssistSection",
    "KBExtractionInput",
    "KBExtractionItem",
    "KBExtractionResult",
    "KBImproveSection",
    "KBImproveSuggestionSection",
    "KBMergeDecisionSection",
    "KBMergeSection",
    "KBMergeStrategySection",
    "KBOperationsInput",
    "KBOperationsResult",
    "NameGenerationInput",
    "NameGenerationResult",
    "OutlineSection",
    "POVMetricsIssue",
    "POVMetricsScene",
    "POVSection",
    "PlanningStructureInput",
    "PlanningStructureResult",
    "PreferenceAnalysisInput",
    "PreferenceAnalysisResult",
    "ReadabilitySection",
    "RewriteSelectionInput",
    "RewriteSelectionResult",
    "SummarySection",
    "TimelineEventSection",
    "TimelineSection",
    "WorldbuildingConnectionSection",
    "WorldbuildingGapSection",
    "WorldbuildingSection",
    "WritingProseInput",
    "WritingProseResult",
]


class KBExtractionInput(BaseModel):
    """Input for KB extraction eval cases."""

    chapter_title: str
    genre: str
    chapter_text: str
    existing_entity_names: list[str] = Field(default_factory=list)


class KBExtractionItem(BaseModel):
    """Normalized KB extraction result used by evals."""

    item_type: Literal["new_entity", "update_entity", "relationship", "conflict"]
    name: str
    entity_type: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_text: str = ""


def _empty_kb_items() -> list[KBExtractionItem]:
    """Return a typed empty extraction item list."""

    return []


class KBExtractionResult(BaseModel):
    """Normalized KB extraction output."""

    results: list[KBExtractionItem] = Field(default_factory=_empty_kb_items)
    analysis_notes: str = ""


class RewriteSelectionInput(BaseModel):
    """Input for rewrite selection eval cases."""

    selection_text: str
    context_before: str = ""
    context_after: str = ""
    rewrite_mode: Literal["tone", "style", "voice", "fix", "custom"]
    instruction: str
    genre: str = "Fantasy"


class RewriteSelectionResult(BaseModel):
    """Structured rewrite selection result."""

    selected_mode: str
    rewritten_text: str
    rationale: str = ""


class PreferenceAnalysisInput(BaseModel):
    """Input for preference analysis eval cases."""

    genre: str
    feedback_text: str
    event_count: int


class PreferenceAnalysisResult(BaseModel):
    """Normalized preference analysis output."""

    style_patterns: list[str] = Field(default_factory=list)
    content_patterns: list[str] = Field(default_factory=list)
    avoidance_patterns: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = ""


# ---------------------------------------------------------------------------
# chat_generation suite
# ---------------------------------------------------------------------------


class DraftOutputField(BaseModel):
    """Subset of DraftOutput fields used by chat_generation eval for draft type."""

    text: str
    title: str | None = None
    scene_breaks: list[int] = []
    word_count: int = 0
    metadata: dict[str, Any] = {}


class ChatGenerationInput(BaseModel):
    """Input for chat/agent eval cases."""

    agent_type: Literal["chat", "draft", "inline_suggest"]
    prompt_text: str
    genre: str = "Fantasy"
    language: str = "en"


class ChatGenerationResult(BaseModel):
    """Normalized chat/agent generation result."""

    text: str
    draft_output: DraftOutputField | None = None  # only for draft_agent
    word_count: int = 0


# ---------------------------------------------------------------------------
# analysis_feedback suite
# ---------------------------------------------------------------------------


class AnalysisFeedbackInput(BaseModel):
    """Input for analysis/feedback agent eval cases."""

    agent_type: Literal["beta_reader", "review", "consistency"]
    text_content: str
    genre: str = "Fantasy"
    language: str = "en"


class AnalysisFeedbackResult(BaseModel):
    """Normalized analysis/feedback result."""

    passed: bool = False
    issues_found: int = 0
    quality_score: int = 0
    summary: str = ""


# ---------------------------------------------------------------------------
# analysis_metrics suite
#
# Three analysis-panel agents (Readability, POV, ChapterSummary) have
# structurally different outputs. Mirroring the chat_generation pattern
# (which carries an optional ``draft_output`` for one agent variant), the
# analysis_metrics result is a union model with one optional section per
# agent. Exactly one section is populated, matching the case's agent_type.
# Evaluators are metadata-aware (check ``agent_type``) and return 1.0 when
# not applicable, exactly like ``ChatDraftStructureMatch``.
# ---------------------------------------------------------------------------


class POVMetricsScene(BaseModel):
    """Subset of POVDetectedScene fields used by analysis_metrics eval.

    Mirrors ``narrare_core.agents.pov_types.POVDetectedScene``.
    """

    scene_index: int = 0
    pov_character: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    text_sample: str = ""


class POVMetricsIssue(BaseModel):
    """Subset of POVDetectedIssue fields used by analysis_metrics eval.

    Mirrors ``narrare_core.agents.pov_types.POVDetectedIssue``.
    """

    type: str = ""
    location: str = ""
    text: str = ""
    explanation: str = ""
    suggestion: str = ""
    severity: str = "warning"


def _empty_problematic_sentences() -> list[dict[str, Any]]:
    """Return a typed empty readability sentence list."""

    return []


def _empty_pov_scenes() -> list[POVMetricsScene]:
    """Return a typed empty POV scene list."""

    return []


def _empty_pov_issues() -> list[POVMetricsIssue]:
    """Return a typed empty POV issue list."""

    return []


def _empty_summary_key_points() -> list[str]:
    """Return a typed empty key-points list."""

    return []


def _empty_summary_metadata() -> dict[str, Any]:
    """Return a typed empty summary metadata mapping."""

    return {}


class ReadabilitySection(BaseModel):
    """Readability agent output section.

    Mirrors ``narrare_core.agents.readability_types.ReadabilityAgentOutput``.
    ``problematic_sentences`` keeps the untyped dict shape of the source model
    (each dict carries ``content``/``sentence``, ``issues``, ``suggestions``).
    """

    overall_assessment: str = ""
    problematic_sentences: list[dict[str, Any]] = Field(
        default_factory=_empty_problematic_sentences
    )


class POVSection(BaseModel):
    """POV detection agent output section.

    Mirrors ``narrare_core.agents.pov_types.POVDetectionOutput``.
    """

    scenes: list[POVMetricsScene] = Field(default_factory=_empty_pov_scenes)
    issues: list[POVMetricsIssue] = Field(default_factory=_empty_pov_issues)
    pov_distribution: dict[str, float] = Field(default_factory=dict)
    switch_count: int = 0
    analysis_type: str = ""
    overall_assessment: str = ""


class SummarySection(BaseModel):
    """Chapter summary agent output section.

    Mirrors ``narrare_core.agents.summary_types.SummaryOutput``.
    """

    summary: str = ""
    key_points: list[str] = Field(default_factory=_empty_summary_key_points)
    word_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=_empty_summary_metadata)


class AnalysisMetricsInput(BaseModel):
    """Input for analysis metrics eval cases."""

    agent_type: Literal["readability", "pov", "summary"]
    text_content: str
    genre: str = "Fantasy"
    language: str = "en"


class AnalysisMetricsResult(BaseModel):
    """Union result for the analysis_metrics eval suite.

    Exactly one section is populated, matching the case's ``agent_type``.
    """

    readability: ReadabilitySection | None = None
    pov: POVSection | None = None
    summary: SummarySection | None = None


# ---------------------------------------------------------------------------
# planning_structure suite
#
# Models live in ``evals/models_planning.py`` (extracted to keep this module
# within the RULE-04 file-size limit — architectural-discipline: file-size
# limits force modularization, not compression). They are re-exported here so
# existing ``from evals.models import ...`` imports keep working. See
# ``models_planning.py`` for the authoritative docstrings and the
# plan-vs-reality note (OutlineAgent has no "variant count" concept).
# ---------------------------------------------------------------------------
