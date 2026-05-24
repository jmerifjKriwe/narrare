"""Output types for KBAssistAgent.

See design.md D2 — single model with mode discriminator.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class KBAssistOutput(BaseModel):
    """Structured output of a KBAssistAgent run.

    The agent operates in 4 modes:
    - question: Ask the user a focused question about one template field
    - suggestion: Suggest a value for a specific field
    - draft: Generate a partial entity entry with multiple fields
    - complete: Finalize the entity entry

    Attributes:
        mode: Which interaction mode this response uses.
        question: The question to ask (question mode only).
        field_key: Template field this response targets (question/suggest mode).
        suggestion: Suggested value for a field (suggestion mode only).
        reasoning: Chain-of-thought explanation of why this response.
        context_used: Names of KB entities referenced in this response.
        draft_entry: Partial entity data dict (draft mode).
        final_entry: Complete entity data dict (complete mode).
        progress: Completion progress 0.0-1.0 (draft/complete mode).
    """

    mode: Literal["question", "suggestion", "draft", "complete"]
    question: str | None = None
    field_key: str | None = None
    suggestion: str | None = None
    reasoning: str | None = None
    context_used: list[str] | None = None
    draft_entry: dict[str, Any] | None = None
    final_entry: dict[str, Any] | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
