"""Types and deps for DraftAgent.

Siehe ADR-015 Phase 2.1 — Output Types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from narrare_core.writing.context_assembler import WritingContextAssembler


class DraftDeps:
    """Dependencies for DraftAgent.

    Attributes:
        context_assembler: Provides 5-tier context assembly for writing.
        preference_service: User preferences for style, tone, etc. (Phase 3+).
    """

    def __init__(
        self,
        context_assembler: WritingContextAssembler | None = None,
    ) -> None:
        self.context_assembler = context_assembler


class DraftOutput(BaseModel):
    """Strukturierter Output eines Draft-Agent-Durchlaufs.

    Attributes:
        text: The generated draft text.
        title: Optional chapter title suggested by the model.
        scene_breaks: Character positions of scene breaks (***).
        word_count: Total word count of the cleaned text.
        metadata: Additional metadata (model, tokens, duration, etc.)
    """

    text: str
    title: str | None = None
    scene_breaks: list[int] = []
    word_count: int = 0
    metadata: dict[str, Any] = {}


class DraftConfig(BaseModel):
    """Konfiguration für einen Draft-Durchlauf.

    Attributes:
        mode: Draft generation mode.
        tone: Optional tone instruction (e.g. "dark", "humorous").
        max_tokens: Maximum output tokens.
        word_target: Optional target word count for enforcement.
    """

    mode: str = "full_draft"
    tone: str | None = None
    max_tokens: int = 8192
    word_target: int | None = None
