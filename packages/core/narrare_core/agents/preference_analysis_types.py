"""Output types for the PreferenceAnalysis agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PreferenceAnalysisOutput(BaseModel):
    """Structured output from PreferenceAnalysisAgent."""

    style_patterns: list[str] = Field(
        default_factory=list,
        description="Detected style patterns (e.g. 'prefers concise sentences')",
    )
    content_patterns: list[str] = Field(
        default_factory=list,
        description="Content preferences (e.g. 'favors dialogue over description')",
    )
    avoidance_patterns: list[str] = Field(
        default_factory=list,
        description="Things the user avoids (e.g. 'dislikes cliffhangers')",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the analysis",
    )
    summary: str = Field(
        default="",
        description="Brief human-readable summary of the preference profile",
    )
