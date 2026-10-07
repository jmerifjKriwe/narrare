"""Provider schemas (Task 10.1) — AI provider management models.

RULE-04 split from ``schemas.py``: request/response models for AI
provider management (create, update, masked response). The names are
re-exported from ``narrare.settings.schemas`` so existing import paths
stay stable.
"""

from __future__ import annotations

import uuid  # noqa: TC003 - needed at runtime for Pydantic model resolution
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


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
    base_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
