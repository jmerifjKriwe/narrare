"""Token limits Pydantic schemas.

Request/response models for the token limits endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TokenLimitOverridesResponse(BaseModel):
    """Fully resolved token limit configuration.

    Returned by the GET endpoint after merging all layers.
    """

    model_config = ConfigDict(from_attributes=True)

    output_limit: int = 4096
    token_profile: str = "balanced"
    tier_percentages: dict[str, float] = Field(
        default_factory=lambda: {
            "immediate": 0.30,
            "recent": 0.20,
            "kb_referenced": 0.25,
            "kb_suggested": 0.15,
            "pinned": 0.10,
        }
    )
    ws_timeout: int = 1800
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    max_selection_words: int = 2000


class UpdateTokenLimitsRequest(BaseModel):
    """Partial update request for token limit overrides.

    All fields are optional — only provided fields are persisted.
    """

    output_limit: int | None = Field(default=None, ge=1, le=131072)
    token_profile: str | None = Field(
        default=None,
        pattern=r"^(quick|balanced|long_texts|custom)$",
    )
    tier_percentages: dict[str, float] | None = None
    ws_timeout: int | None = Field(default=None, ge=60, le=86400)
    retry_max_attempts: int | None = Field(default=None, ge=1, le=20)
    retry_base_delay: float | None = Field(default=None, ge=0.1, le=60.0)
