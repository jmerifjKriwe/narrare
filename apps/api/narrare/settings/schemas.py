"""Settings Pydantic schemas.

Contains request/response models for all settings endpoints:
- User settings (display name, language, theme)
- Project settings (autosave, language, legacy AI fields) — see
  schemas_project_settings.py (RULE-04 split)
- AI settings (default model, category/intent overrides, token limits)
- Project AI overrides
- AI provider management — see schemas_providers.py (RULE-04 split)
- Custom tones — see schemas_tones.py (RULE-04 split)
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003 - needed at runtime for Pydantic model resolution
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from narrare.settings.schemas_project_settings import (
    ProjectSettingsResponse,
    UpdateProjectSettingsRequest,
    WritingGoalsPayload,
)
from narrare.settings.schemas_providers import (
    CreateProviderRequest,
    ProviderResponse,
    UpdateProviderRequest,
)
from narrare.settings.schemas_tones import CustomTone  # noqa: TC001 — used in Pydantic annotation

# RULE-04 split: explicit re-export of the provider + project-settings
# schemas so downstream importers of ``narrare.settings.schemas`` stay
# type-visible for pyright (reportPrivateImportUsage) and ruff (F401)
# without suppression pragmas.
__all__ = [
    "CreateProviderRequest",
    "ProjectSettingsResponse",
    "ProviderResponse",
    "UpdateProjectSettingsRequest",
    "UpdateProviderRequest",
    "WritingGoalsPayload",
]

# ---------------------------------------------------------------------------
# Existing schemas (user settings, project settings)
# ---------------------------------------------------------------------------


class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: uuid.UUID
    display_name: str
    ui_language: str
    theme: str
    custom_tones: list[CustomTone] = []
    updated_at: datetime


class UpdateUserSettingsRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    ui_language: str | None = Field(default=None, min_length=2, max_length=10)
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")
    custom_tones: list[dict[str, object]] | None = Field(
        default=None, description="Full replacement list of custom tones"
    )


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
    embedding_provider: str = "auto"
    embedding_model: str | None = None
    active_embedding_tier: str | None = None
    # STATS-002 budgets (ADR-094, spec A-7). monthly_budget_usd mirrors the
    # nullable NUMERIC(10,2) column (NULL = no budget → gate no-op);
    # budget_mode defaults to the column default 'warn'.
    monthly_budget_usd: Decimal | None = None
    budget_mode: str = "warn"
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
    embedding_provider: str | None = Field(
        default=None,
        max_length=20,
        description="Embedding provider: auto, openai, local, or disabled",
    )
    embedding_model: str | None = Field(
        default=None,
        max_length=100,
        description="Custom embedding model name (null = use default)",
    )
    # STATS-002 budgets (ADR-094, spec A-7): nullable Decimal ≥ 0 mirroring
    # NUMERIC(10,2) — negative/garbage/overflow ⇒ 422 (pydantic → FastAPI
    # RequestValidationError). Explicit null = unset (the service
    # distinguishes it from "not provided" via model_fields_set).
    monthly_budget_usd: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
        description="Monthly spend cap in USD (null = no budget)",
    )
    budget_mode: Literal["warn", "block"] | None = Field(
        default=None,
        description="Enforcement mode: warn (badge only) or block (hard stop)",
    )

    @field_validator("budget_mode")
    @classmethod
    def _reject_null_budget_mode(
        cls, value: Literal["warn", "block"] | None
    ) -> Literal["warn", "block"] | None:
        """Explicit ``null`` is not a valid budget_mode ⇒ 422.

        The column is NOT NULL and "unset" is meaningless for the
        enforcement mode (only ``monthly_budget_usd`` is nullable), so an
        explicit ``{"budget_mode": null}`` payload would otherwise reach
        the DB as an IntegrityError (500). Pydantic skips field
        validators for not-provided defaults, so omitting the field
        ("not provided" → keep current mode) stays valid.
        """
        if value is None:
            raise ValueError("budget_mode cannot be null — omit the field to keep the current mode")
        return value


class ProjectAiSettingsResponse(BaseModel):
    """Project-level AI overrides."""

    model_config = ConfigDict(from_attributes=True)

    novel_id: uuid.UUID
    category_overrides: dict[str, object]
    intent_overrides: dict[str, object]
    updated_at: datetime


class UpdateProjectAiSettingsRequest(BaseModel):
    """Request to update project AI overrides.

    All fields are optional — only provided fields are updated.
    """

    category_overrides: dict[str, object] | None = None
    intent_overrides: dict[str, object] | None = None
