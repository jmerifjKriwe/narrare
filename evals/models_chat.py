"""Eval models for the chat_generation suite.

Extracted from ``evals/models.py`` per RULE-04 (modularize, do not compress)
to mirror ``models_writing.py`` / ``models_planning.py`` /
``models_kb_operations.py``. The models are re-exported from
``evals.models`` so existing ``from evals.models import ...`` imports keep
working.

``DraftOutputField`` is a subset of ``DraftOutput`` fields used by the
chat_generation eval for draft typing (the full production model is not
needed to grade generation quality); ``draft_output`` on the result is
populated only for the ``draft`` agent variant.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

__all__ = [
    "ChatGenerationInput",
    "ChatGenerationResult",
    "DraftOutputField",
]


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
