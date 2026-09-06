"""Authoritative token-limit profile contract for Core LLM settings.

CR-08 P1 makes this module the single Core source of truth for public token
profile vocabulary, preset output limits, custom-mode semantics, and legacy
profile normalization.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class TokenLimitProfile(StrEnum):
    """Public token-limit profiles accepted by the CR-08 P1 contract."""

    QUICK = "quick"
    BALANCED = "balanced"
    LONG_TEXTS = "long_texts"
    COMPREHENSIVE = "comprehensive"
    CUSTOM = "custom"


TOKEN_OUTPUT_ABSOLUTE_MAX: Final[int] = 131072
"""Largest raw output limit accepted before provider-specific calibration."""

TOKEN_OUTPUT_UX_RECOMMENDED_MAX: Final[int] = 16000
"""Recommended UX slider range; not a provider or API hard maximum."""

PUBLIC_TOKEN_LIMIT_PROFILES: tuple[TokenLimitProfile, ...] = (
    TokenLimitProfile.QUICK,
    TokenLimitProfile.BALANCED,
    TokenLimitProfile.LONG_TEXTS,
    TokenLimitProfile.COMPREHENSIVE,
    TokenLimitProfile.CUSTOM,
)
"""Ordered public profile vocabulary. Do not include legacy aliases here."""

TOKEN_PRESET_PROFILE_VALUES: tuple[str, ...] = (
    TokenLimitProfile.QUICK.value,
    TokenLimitProfile.BALANCED.value,
    TokenLimitProfile.LONG_TEXTS.value,
    TokenLimitProfile.COMPREHENSIVE.value,
)
"""Profiles with fixed preset output limits. ``custom`` is intentionally absent."""

PROFILE_OUTPUT_LIMITS: dict[str, int] = {
    TokenLimitProfile.QUICK.value: 500,
    TokenLimitProfile.BALANCED.value: 2000,
    # Raised 16000 → 32000 (benchmark finding): ch-11 KB extraction on the
    # reveal chapter — the densest in the corpus — exhausted the 16000
    # output-token ceiling before emitting its full structured payload.
    # comprehensive follows to keep the preset ladder consistent.
    TokenLimitProfile.LONG_TEXTS.value: 32000,
    TokenLimitProfile.COMPREHENSIVE.value: 32000,
}
"""Preset output-token limits for non-custom profiles."""

TOKEN_PROFILE_MINIMUM_OUTPUT_FLOORS: dict[str, int] = {
    TokenLimitProfile.QUICK.value: 128,
    TokenLimitProfile.BALANCED.value: 512,
    TokenLimitProfile.LONG_TEXTS.value: 2048,
    TokenLimitProfile.COMPREHENSIVE.value: 4096,
}
"""Minimum viable output floors for model suitability checks."""


@dataclass(frozen=True, slots=True)
class TokenUsageLimitPreset:
    """Run-level pydantic-ai usage limits associated with a token profile."""

    request_limit: int
    total_tokens_limit: int


TOKEN_PROFILE_USAGE_LIMITS: dict[str, TokenUsageLimitPreset] = {
    TokenLimitProfile.QUICK.value: TokenUsageLimitPreset(
        request_limit=10,
        total_tokens_limit=16000,
    ),
    TokenLimitProfile.BALANCED.value: TokenUsageLimitPreset(
        request_limit=25,
        total_tokens_limit=64000,
    ),
    TokenLimitProfile.LONG_TEXTS.value: TokenUsageLimitPreset(
        request_limit=25,
        total_tokens_limit=128000,
    ),
    TokenLimitProfile.COMPREHENSIVE.value: TokenUsageLimitPreset(
        request_limit=25,
        total_tokens_limit=256000,
    ),
    TokenLimitProfile.CUSTOM.value: TokenUsageLimitPreset(
        request_limit=25,
        total_tokens_limit=64000,
    ),
}
"""Usage-limit presets. ``custom`` keeps balanced run-level safeguards."""

_LEGACY_PROFILE_NORMALIZATION: dict[str, str] = {
    "conservative": TokenLimitProfile.BALANCED.value,
}


def public_token_profile_values() -> tuple[str, ...]:
    """Return the ordered public token profile values."""

    return tuple(profile.value for profile in PUBLIC_TOKEN_LIMIT_PROFILES)


def is_public_token_profile(profile: str | TokenLimitProfile) -> bool:
    """Return whether *profile* is part of the public CR-08 P1 vocabulary."""

    return str(profile) in public_token_profile_values()


def normalize_legacy_token_profile(profile: str | TokenLimitProfile | None) -> str | None:
    """Normalize retired persisted aliases at explicit compatibility boundaries."""

    if profile is None:
        return None
    value = str(profile)
    return _LEGACY_PROFILE_NORMALIZATION.get(value, value)


def is_custom_token_limit_profile(profile: str | TokenLimitProfile | None) -> bool:
    """Return whether *profile* selects raw manual output-limit mode."""

    if profile is None:
        return False
    return str(profile) == TokenLimitProfile.CUSTOM.value


def get_preset_output_limit(profile: str | TokenLimitProfile | None) -> int | None:
    """Return the preset output limit for non-custom profiles, if defined."""

    if profile is None:
        return None
    return PROFILE_OUTPUT_LIMITS.get(str(profile))


def resolve_output_limit_for_profile(
    profile: str | TokenLimitProfile | None,
    *,
    raw_output_limit: int,
) -> int:
    """Resolve effective output tokens from profile selection and raw limit.

    Preset profiles use their configured output limit. ``custom`` and unknown
    values use the raw limit supplied by the caller, preserving compatibility
    with existing configuration objects while keeping public validation outside
    this helper.
    """

    preset_limit = get_preset_output_limit(profile)
    if preset_limit is not None:
        return preset_limit
    return raw_output_limit


def get_usage_limit_preset(
    profile: str | TokenLimitProfile | None,
    *,
    normalize_legacy: bool = False,
) -> TokenUsageLimitPreset | None:
    """Return run-level usage limits for a token profile.

    Legacy aliases are recognized only when *normalize_legacy* is explicitly
    enabled by a compatibility boundary.
    """

    if profile is None:
        return None
    value = normalize_legacy_token_profile(profile) if normalize_legacy else str(profile)
    if value is None:
        return None
    return TOKEN_PROFILE_USAGE_LIMITS.get(value)
