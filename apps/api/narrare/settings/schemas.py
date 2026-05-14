"""Settings Pydantic schemas.

Contains request/response models for all settings endpoints:
- User settings (display name, language, theme)
- Project settings (autosave, language, legacy AI fields)
- AI provider management (create, update, masked response)
- AI settings (default model, category/intent overrides, token limits)
- Project AI overrides
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Existing schemas (user settings, project settings)
# ---------------------------------------------------------------------------


class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: uuid.UUID
    display_name: str
    ui_language: str
    theme: str
    updated_at: datetime


class UpdateUserSettingsRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    ui_language: str | None = Field(default=None, min_length=2, max_length=10)
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")


class ProjectSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    novel_id: uuid.UUID
    autosave_interval: int
    default_language: str
    ai_provider: str
    ai_model: str
    model_overrides: str
    category_overrides: dict[str, object]
    intent_overrides: dict[str, object]
    token_limit_overrides: dict[str, object]
    updated_at: datetime


class UpdateProjectSettingsRequest(BaseModel):
    autosave_interval: int | None = Field(default=None, ge=0, le=3600)
    default_language: str | None = Field(default=None, min_length=2, max_length=10)
    ai_provider: str | None = Field(default=None, max_length=50)
    ai_model: str | None = Field(default=None, max_length=200)
    model_overrides: str | None = None  # JSON string


# ---------------------------------------------------------------------------
# Provider schemas (Task 10.1)
# ---------------------------------------------------------------------------


class CreateProviderRequest(BaseModel):
    """Request to register a new AI provider."""

    provider_name: str = Field(
        max_length=50, description="Provider name, e.g. 'anthropic', 'openrouter'"
    )
    api_key: str = Field(min_length=1, description="API key for the provider")
    base_url: str | None = Field(
        default=None,
        max_length=500,
        description="Custom base URL for OpenAI-compatible providers",
    )


class UpdateProviderRequest(BaseModel):
    """Request to update an existing provider's credentials or status."""

    api_key: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class ProviderResponse(BaseModel):
    """Provider entry with masked API key — never exposes the full key."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_name: str
    has_api_key: bool
    api_key_last4: str
    base_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# AI settings schemas (Task 10.2)
# ---------------------------------------------------------------------------


class UserAiSettingsResponse(BaseModel):
    """User-level AI configuration."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    default_provider_id: uuid.UUID | None
    default_model: str
    category_overrides: dict[str, object]
    intent_overrides: dict[str, object]
    token_limit_profile: str
    token_limit_overrides: dict[str, object]
    updated_at: datetime


class UpdateUserAiSettingsRequest(BaseModel):
    """Request to update user AI settings.

    All fields are optional — only provided fields are updated.
    Provider references are validated before persisting.
    """

    default_provider_id: uuid.UUID | None = None
    default_model: str | None = Field(default=None, max_length=200)
    category_overrides: dict[str, object] | None = None
    intent_overrides: dict[str, object] | None = None
    token_limit_profile: str | None = Field(
        default=None,
        pattern=r"^(quick|balanced|long_texts|custom)$",
    )
    token_limit_overrides: dict[str, object] | None = None


class ProjectAiSettingsResponse(BaseModel):
    """Project-level AI overrides."""

    model_config = ConfigDict(from_attributes=True)

    novel_id: uuid.UUID
    category_overrides: dict[str, object]
    intent_overrides: dict[str, object]
    token_limit_overrides: dict[str, object]
    updated_at: datetime


class UpdateProjectAiSettingsRequest(BaseModel):
    """Request to update project AI overrides.

    All fields are optional — only provided fields are updated.
    """

    category_overrides: dict[str, object] | None = None
    intent_overrides: dict[str, object] | None = None
    token_limit_overrides: dict[str, object] | None = None


# ---------------------------------------------------------------------------
# Token limit profile schemas (Task 10.3)
# ---------------------------------------------------------------------------

from narrare_core.llm.override_schemas import TokenLimitOverride  # noqa: E402

TOKEN_LIMIT_PROFILES: dict[str, dict[str, TokenLimitOverride]] = {
    "quick": {
        "default": TokenLimitOverride(max_tokens=500, temperature=0.7),
    },
    "balanced": {
        "default": TokenLimitOverride(max_tokens=2000, temperature=0.7),
    },
    "long_texts": {
        "default": TokenLimitOverride(max_tokens=8000, temperature=0.7),
    },
    "custom": {},
}
"""Pre-defined token limit profiles.

Each profile maps a key (category name or "default") to a
``TokenLimitOverride``. The "custom" profile starts empty — the user
fills in per-category overrides.
"""

VALID_TOKEN_LIMIT_PROFILES: set[str] = set(TOKEN_LIMIT_PROFILES.keys())
