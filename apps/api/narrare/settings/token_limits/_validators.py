"""Token limit override validation — field and profile checks."""

from __future__ import annotations

from narrare_core.shared.errors import ValidationError

# Valid token profile names — matches narrare.settings.token_profiles
# and narrare_core.llm.run_limits.profile_to_usage_limits (6 profiles).
VALID_PROFILES: set[str] = {
    "quick",
    "balanced",
    "long_texts",
    "comprehensive",
    "conservative",
    "custom",
}

# Valid fields that can be overridden
VALID_OVERRIDE_FIELDS: set[str] = {
    "output_limit",
    "token_profile",
    "tier_percentages",
    "ws_timeout",
    "retry_max_attempts",
    "retry_base_delay",
    # Legacy migration key — stores old-format per-category overrides
    # during the SET-005 dual-write transition period.
    "legacy_per_category_overrides",
    # Consistency context caps
    "max_chapter_tokens",
    "max_kb_entries",
    # Co-author selection word limit (SET-005 cascade)
    "max_selection_words",
}


def validate_token_overrides(overrides: dict[str, object]) -> None:
    """Validate override field names and values.

    Args:
        overrides: Dict of fields to validate.

    Raises:
        ValidationError: If a field name is unknown or value is invalid.
    """
    for key, value in overrides.items():
        if key not in VALID_OVERRIDE_FIELDS:
            raise ValidationError(
                f"Unknown token limit override field: {key}",
                code="INVALID_OVERRIDE_FIELD",
            )
        if key == "token_profile" and value not in VALID_PROFILES:
            raise ValidationError(
                f"Invalid token profile: {value}. "
                f"Must be one of: {', '.join(sorted(VALID_PROFILES))}",
                code="INVALID_TOKEN_PROFILE",
            )
