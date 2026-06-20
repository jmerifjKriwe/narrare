"""Token limits Pydantic schemas.

CR-08 P1: profile validation is derived from Core
(:mod:`narrare_core.llm.token_profiles`); this module keeps no independent
vocabulary that could drift. Responses expose the profile catalogue,
absolute/UX caps, requested-vs-effective output limit, and (when a
provider/model/intent is supplied) calibration evidence and suitability
warnings.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from narrare.settings.token_limits.contracts import DEFAULT_TIER_PERCENTAGES
from narrare_core.llm.token_profiles import (
    PROFILE_OUTPUT_LIMITS,
    TOKEN_OUTPUT_ABSOLUTE_MAX,
    TOKEN_OUTPUT_UX_RECOMMENDED_MAX,
    is_custom_token_limit_profile,
    public_token_profile_values,
)

#: Regex anchored on Core's public profile values. Built at import time from
#: the authoritative vocabulary so the write schema cannot drift from Core.
_TOKEN_PROFILE_PATTERN: str = "^(" + "|".join(public_token_profile_values()) + ")$"


# ---------------------------------------------------------------------------
# Catalogue metadata (CR-08 P1 D1 / D4)
# ---------------------------------------------------------------------------


class TokenProfilePreset(BaseModel):
    """One public token-limit profile and its preset output limit (if any)."""

    model_config = ConfigDict(frozen=True)

    value: str
    preset_output_limit: int | None = Field(
        default=None,
        description="Fixed preset output limit; None for the custom mode.",
    )
    is_custom: bool = Field(default=False, description="True for the custom raw mode.")


class TokenLimitsCatalog(BaseModel):
    """Static token-limit vocabulary and caps, derived from Core."""

    model_config = ConfigDict(frozen=True)

    profiles: list[TokenProfilePreset]
    absolute_max: int = Field(
        description="Largest raw output limit accepted before provider calibration."
    )
    ux_recommended_max: int = Field(
        description="Recommended UX slider range; not a provider or API hard maximum."
    )


# ---------------------------------------------------------------------------
# Calibration + suitability metadata (CR-08 P1 D5 / D6)
# ---------------------------------------------------------------------------


class CalibrationSourceMetadata(BaseModel):
    """Typed provider/model calibration evidence for a limit lookup."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model_id: str
    status: str
    source: str
    provider_max_output_tokens: int | None = None
    context_window_tokens: int | None = None
    source_timestamp: float | None = None
    cache_age_seconds: float | None = None
    detail: str | None = None


class SuitabilityIssueMetadata(BaseModel):
    """One suitability finding (advisory / warning / hard_block)."""

    model_config = ConfigDict(frozen=True)

    severity: str
    code: str
    message: str


class SuitabilityMetadata(BaseModel):
    """Suitability decision for one model/intent/output request."""

    model_config = ConfigDict(frozen=True)

    intent: str
    output_profile: str
    requested_output_tokens: int
    effective_output_tokens: int
    recommended_output_tokens: int
    minimum_viable_output_tokens: int
    calibration_status: str
    provider_max_output_tokens: int | None
    severity: str
    is_allowed: bool
    issues: list[SuitabilityIssueMetadata]


# ---------------------------------------------------------------------------
# Resolved-limits response
# ---------------------------------------------------------------------------


class TokenLimitOverridesResponse(BaseModel):
    """Fully resolved token limit configuration plus CR-08 P1 metadata.

    Returned by the GET endpoint after merging all layers. ``output_limit``
    is the *requested* raw limit; ``effective_output_limit`` applies the
    resolved profile semantics. ``metadata`` always carries the Core-derived
    catalogue and caps; ``calibration``/``suitability`` are populated when
    the caller supplies provider/model/intent query parameters.
    """

    model_config = ConfigDict(from_attributes=True)

    output_limit: int = 4096
    token_profile: str = "balanced"
    effective_output_limit: int = 2000
    tier_percentages: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_TIER_PERCENTAGES)
    )
    ws_timeout: int = 1800
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    metadata: TokenLimitsCatalog
    calibration: CalibrationSourceMetadata | None = None
    suitability: SuitabilityMetadata | None = None


# ---------------------------------------------------------------------------
# Write request
# ---------------------------------------------------------------------------


class UpdateTokenLimitsRequest(BaseModel):
    """Partial update request for token limit overrides.

    All fields are optional — only provided fields are persisted. The
    ``token_profile`` pattern is derived from Core's public vocabulary; the
    retired ``conservative`` alias is rejected here.
    """

    output_limit: int | None = Field(default=None, ge=1, le=TOKEN_OUTPUT_ABSOLUTE_MAX)
    token_profile: str | None = Field(default=None, pattern=_TOKEN_PROFILE_PATTERN)
    tier_percentages: dict[str, float] | None = None
    ws_timeout: int | None = Field(default=None, ge=60, le=86400)
    retry_max_attempts: int | None = Field(default=None, ge=1, le=20)
    retry_base_delay: float | None = Field(default=None, ge=0.1, le=60.0)


def build_catalog() -> TokenLimitsCatalog:
    """Build the Core-derived token-limit catalogue for API responses."""

    profiles: list[TokenProfilePreset] = []
    for value in public_token_profile_values():
        custom = is_custom_token_limit_profile(value)
        profiles.append(
            TokenProfilePreset(
                value=value,
                preset_output_limit=None if custom else PROFILE_OUTPUT_LIMITS[value],
                is_custom=custom,
            )
        )
    return TokenLimitsCatalog(
        profiles=profiles,
        absolute_max=TOKEN_OUTPUT_ABSOLUTE_MAX,
        ux_recommended_max=TOKEN_OUTPUT_UX_RECOMMENDED_MAX,
    )
