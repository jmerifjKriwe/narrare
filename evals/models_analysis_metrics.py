"""Eval models for the analysis_metrics suite.

Extracted from ``evals/models.py`` per RULE-04 (modularize, do not compress)
to mirror ``models_writing.py`` / ``models_planning.py`` /
``models_kb_operations.py``. The models are re-exported from
``evals.models`` so existing ``from evals.models import ...`` imports keep
working.

Three analysis-panel agents (Readability, POV, ChapterSummary) have
structurally different outputs. Mirroring the chat_generation pattern
(which carries an optional ``draft_output`` for one agent variant), the
analysis_metrics result is a union model with one optional section per
agent. Exactly one section is populated, matching the case's agent_type.
Evaluators are metadata-aware (check ``agent_type``) and return 1.0 when
not applicable, exactly like ``ChatDraftStructureMatch``.

Each section mirrors its authoritative agent output type:

- ReadabilitySection → ``narrare_core.agents.readability_types.ReadabilityAgentOutput``
- POVSection         → ``narrare_core.agents.pov_types.POVDetectionOutput``
- POVMetricsScene    → ``narrare_core.agents.pov_types.POVDetectedScene``
- POVMetricsIssue    → ``narrare_core.agents.pov_types.POVDetectedIssue``
- SummarySection     → ``narrare_core.agents.summary_types.SummaryOutput``
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

__all__ = [
    "AnalysisMetricsInput",
    "AnalysisMetricsResult",
    "POVMetricsIssue",
    "POVMetricsScene",
    "POVSection",
    "ReadabilitySection",
    "SummarySection",
]


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
