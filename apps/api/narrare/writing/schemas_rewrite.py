"""Writing rewrite schemas — rewrite-specific request/response models.

Split from schemas.py per RULE-04 (file size limit).
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for Pydantic model resolution
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class RewriteMode(StrEnum):
    """Supported rewrite modes."""

    TONE = "tone"
    STYLE = "style"
    VOICE = "voice"
    FIX = "fix"
    CUSTOM = "custom"


class RewriteRequest(BaseModel):
    """Request for rewriting a text selection with alternatives.

    The frontend sends the selected text along with optional context
    before/after and a rewrite mode.  The backend streams one or more
    alternatives wrapped in ``<alternative>`` tags via SSE.
    """

    selection_text: str = Field(
        ...,
        min_length=50,
        max_length=2000,
        description="Text to rewrite",
    )
    context_before: str | None = Field(
        default=None,
        max_length=500,
        description="Text before selection (up to 500 chars)",
    )
    context_after: str | None = Field(
        default=None,
        max_length=500,
        description="Text after selection (up to 500 chars)",
    )
    mode: RewriteMode = Field(
        ...,
        description="Rewrite mode (tone, style, voice, fix, custom)",
    )
    options: dict[str, str] | None = Field(
        default=None,
        description="Mode-specific settings",
    )
    character_id: uuid.UUID | None = Field(
        default=None,
        description="Character ID for voice mode",
    )
    custom_instructions: str | None = Field(
        default=None,
        max_length=500,
        description="Custom rewrite instructions",
    )
    count: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Number of alternatives (1-3)",
    )
    tone: str = Field(
        default="balanced",
        min_length=1,
        max_length=100,
        description="Tone preference",
    )
    language: str = Field(
        default="en",
        min_length=2,
        max_length=5,
        description="Output language",
    )

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> RewriteRequest:
        """Ensure mode-specific required fields are present.

        - ``voice`` mode requires ``character_id``.
        - ``custom`` mode requires ``custom_instructions``.
        """
        if self.mode == RewriteMode.VOICE and not self.character_id:
            raise ValueError("character_id is required when mode is 'voice'")
        if self.mode == RewriteMode.CUSTOM and not self.custom_instructions:
            raise ValueError("custom_instructions is required when mode is 'custom'")
        return self


class ContextMetaResponse(BaseModel):
    """Context metadata sent as first SSE event before text streaming (CR-07)."""

    type: str = "context_meta"
    kb_characters_count: int = 0
    kb_locations_count: int = 0
    kb_factions_count: int = 0
    kb_suggested_count: int = 0
    kb_pinned_count: int = 0
    recent_chapter_count: int = 0
    character_names: list[str] = []
    location_names: list[str] = []
    faction_names: list[str] = []
    is_first_chapter: bool = False
    has_user_preferences: bool = False
    tone: str = "balanced"
    total_budget_tokens: int = 0
