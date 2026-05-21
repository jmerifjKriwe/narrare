"""Token limit profiles for AI settings.

Pre-defined profiles that map category names to ``TokenLimitOverride`` values.
"""

from __future__ import annotations

from narrare_core.llm.override_schemas import TokenLimitOverride

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
