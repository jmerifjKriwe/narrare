"""
Pydantic schemas for model routing overrides.

These schemas validate the JSONB columns in ``user_ai_settings`` and
``project_settings`` that store per-category, per-intent, and token
limit overrides.

All schemas use plain Pydantic ``BaseModel`` — no ORM mode, no DB
dependencies. They are validated on read AND write to prevent schema
drift between Pydantic and the actual JSONB content.

See: openspec/changes/configurable-model-routing/design.md (D5)
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003  # Pydantic needs UUID at runtime for validation

from pydantic import BaseModel, Field


class CategoryOverride(BaseModel):
    """Override model selection for an entire intent category.

    Stored in ``category_overrides`` JSONB keyed by category name::

        {"writing": {"provider_id": "...", "model_id": "..."}}

    Attributes:
        provider_id: Reference to a ``user_providers`` entry.
        model_id: Model identifier as known to that provider.
    """

    provider_id: UUID
    model_id: str


class IntentOverride(BaseModel):
    """Override model selection for a single intent.

    Stored in ``intent_overrides`` JSONB keyed by intent name::

        {"write": {"provider_id": "...", "model_id": "..."}}

    Intent-level overrides take precedence over category-level overrides.

    Attributes:
        provider_id: Reference to a ``user_providers`` entry.
        model_id: Model identifier as known to that provider.
    """

    provider_id: UUID
    model_id: str


class TokenLimitOverride(BaseModel):
    """Override token limits for a category or intent.

    Stored in ``token_limit_overrides`` JSONB keyed by category/intent name::

        {"writing": {"max_tokens": 8000, "temperature": 0.9}}

    Attributes:
        max_tokens: Maximum tokens in the response. Must be >= 1.
        temperature: Sampling temperature. Must be between 0.0 and 2.0.
    """

    max_tokens: int = Field(ge=1, description="Maximum response tokens")
    temperature: float = Field(
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0-2.0)",
    )
