"""Typed case inputs and outputs for Narrare eval suites."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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
