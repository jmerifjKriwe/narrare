"""Eval models for the preference_analysis suite.

Extracted from ``evals/models.py`` per RULE-04 (modularize, do not compress)
to mirror ``models_writing.py`` / ``models_planning.py`` /
``models_kb_operations.py``. The models are re-exported from
``evals.models`` so existing ``from evals.models import ...`` imports keep
working.

The preference_analysis suite evaluates preference extraction from reader
feedback events: ``PreferenceAnalysisInput`` carries the feedback text plus
the event count the analysis was based on, and the normalized output splits
detected patterns into style / content / avoidance buckets with a confidence
score (consumed by the ``PreferencePatternQuality`` evaluator).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = [
    "PreferenceAnalysisInput",
    "PreferenceAnalysisResult",
]


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
