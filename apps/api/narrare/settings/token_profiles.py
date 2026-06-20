"""Token limit profiles for AI settings.

CR-08 P1 D1: the profile keys are derived from Core's authoritative
vocabulary (:mod:`narrare_core.llm.token_profiles`) so this per-category
preset map cannot drift from the public profile contract. The retired
``conservative`` alias is intentionally absent (D2).

Each preset profile maps the ``"default"`` category to a
:class:`TokenLimitOverride` whose ``max_tokens`` equals Core's preset output
limit. The ``"custom"`` profile starts empty — the user fills in per-category
overrides.
"""

from __future__ import annotations

from narrare_core.llm.override_schemas import TokenLimitOverride
from narrare_core.llm.token_profiles import (
    PROFILE_OUTPUT_LIMITS,
    TOKEN_PRESET_PROFILE_VALUES,
    TokenLimitProfile,
)

_DEFAULT_TEMPERATURE = 0.7


def _build_profiles() -> dict[str, dict[str, TokenLimitOverride]]:
    """Build the profile map from Core's preset vocabulary."""

    profiles: dict[str, dict[str, TokenLimitOverride]] = {}
    for profile in TOKEN_PRESET_PROFILE_VALUES:
        profiles[profile] = {
            "default": TokenLimitOverride(
                max_tokens=PROFILE_OUTPUT_LIMITS[profile],
                temperature=_DEFAULT_TEMPERATURE,
            )
        }
    # ``custom`` is a raw manual mode — no preset category overrides.
    profiles[TokenLimitProfile.CUSTOM.value] = {}
    return profiles


TOKEN_LIMIT_PROFILES: dict[str, dict[str, TokenLimitOverride]] = _build_profiles()
"""Pre-defined token limit profiles, keyed by Core's public profile values."""

VALID_TOKEN_LIMIT_PROFILES: set[str] = set(TOKEN_LIMIT_PROFILES.keys())
"""Public profile vocabulary — equals Core's public token profile values."""
