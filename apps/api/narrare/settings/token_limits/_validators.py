"""Token limit override validation — field and profile checks.

CR-08 P1: the valid profile vocabulary is derived from Core
(:mod:`narrare_core.llm.token_profiles`) so the backend cannot keep an
independent string set that drifts. The retired ``conservative`` alias is
therefore absent here and rejected on writes; legacy persisted values are
normalised at the read boundary instead.
"""

from __future__ import annotations

from narrare_core.llm.token_profiles import public_token_profile_values
from narrare_core.shared.errors import ValidationError

#: Valid public token profile names — derived from Core (CR-08 P1 D1).
#:
#: This is the single backend write-boundary vocabulary. It equals Core's
#: ``public_token_profile_values()`` and intentionally excludes the retired
#: ``conservative`` legacy alias.
VALID_PROFILES: set[str] = set(public_token_profile_values())

# Valid fields that can be overridden
VALID_OVERRIDE_FIELDS: set[str] = {
    "output_limit",
    "token_profile",
    "tier_percentages",
    "ws_timeout",
    # Legacy migration key — stores old-format per-category overrides
    # during the SET-005 dual-write transition period.
    "legacy_per_category_overrides",
    # Consistency context caps
    "max_chapter_tokens",
    "max_kb_entries",
    # Co-author selection word limit (SET-005 cascade)
    "max_selection_words",
    # Input-context budgets (ADR-082 / C5)
    "context_total_budget",
    "series_history_budget",
}

#: Minimum sane values for integer budget keys (write boundary, ADR-082
#: Decision 1 — "ge=1_024-style sanity bounds"). Guards against
#: degenerate overrides (e.g. 1-token totals) without capping ambition.
_INT_FIELD_MINIMA: dict[str, int] = {
    "context_total_budget": 1_024,
    "series_history_budget": 1_024,
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
        minimum = _INT_FIELD_MINIMA.get(key)
        if minimum is not None:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationError(
                    f"Token limit override '{key}' must be an integer, got {type(value).__name__}",
                    code="INVALID_BUDGET_BOUNDS",
                )
            if value < minimum:
                raise ValidationError(
                    f"Token limit override '{key}' must be >= {minimum}, got {value}",
                    code="INVALID_BUDGET_BOUNDS",
                )
