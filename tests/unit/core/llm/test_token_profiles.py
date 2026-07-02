"""CR-08 P1 token profile contract tests."""

from __future__ import annotations

from narrare_core.llm.token_profiles import (
    PROFILE_OUTPUT_LIMITS,
    TOKEN_OUTPUT_ABSOLUTE_MAX,
    TOKEN_OUTPUT_UX_RECOMMENDED_MAX,
    TokenLimitProfile,
    get_preset_output_limit,
    get_usage_limit_preset,
    is_custom_token_limit_profile,
    is_public_token_profile,
    normalize_legacy_token_profile,
    public_token_profile_values,
    resolve_output_limit_for_profile,
)


def test_public_profile_values_match_policy_order() -> None:
    assert public_token_profile_values() == (
        "quick",
        "balanced",
        "long_texts",
        "comprehensive",
        "custom",
    )
    assert [profile.value for profile in TokenLimitProfile] == list(public_token_profile_values())


def test_preset_output_limits_match_policy_and_exclude_custom() -> None:
    assert PROFILE_OUTPUT_LIMITS == {
        "quick": 500,
        "balanced": 2000,
        "long_texts": 8000,
        "comprehensive": 16000,
    }
    assert "custom" not in PROFILE_OUTPUT_LIMITS


def test_token_output_caps_match_policy() -> None:
    assert TOKEN_OUTPUT_ABSOLUTE_MAX == 131072
    assert TOKEN_OUTPUT_UX_RECOMMENDED_MAX == 16000


def test_custom_profile_uses_raw_output_limit() -> None:
    assert is_custom_token_limit_profile("custom") is True
    assert get_preset_output_limit("custom") is None
    assert resolve_output_limit_for_profile("custom", raw_output_limit=32768) == 32768


def test_conservative_is_not_public_but_normalizes_for_legacy_boundaries() -> None:
    assert "conservative" not in public_token_profile_values()
    assert get_preset_output_limit("conservative") is None
    assert normalize_legacy_token_profile("conservative") == "balanced"
    assert normalize_legacy_token_profile("quick") == "quick"


def test_is_public_token_profile_classifies_vocabulary() -> None:
    """The public helper recognises the canonical profile vocabulary."""
    assert is_public_token_profile("balanced") is True
    assert is_public_token_profile("custom") is True
    # Legacy aliases and unknown values are not part of the public vocabulary.
    assert is_public_token_profile("conservative") is False
    assert is_public_token_profile("nonsense") is False


def test_legacy_normalization_passes_none_through() -> None:
    """``None`` (no profile selected) is preserved unchanged."""
    assert normalize_legacy_token_profile(None) is None


def test_custom_check_returns_false_for_no_profile() -> None:
    """No profile selection is not custom manual mode."""
    assert is_custom_token_limit_profile(None) is False


def test_usage_limit_preset_for_none_and_known_profile() -> None:
    """No profile yields no run-level limits; a known profile yields its preset."""
    assert get_usage_limit_preset(None) is None
    preset = get_usage_limit_preset("balanced")
    assert preset is not None
    assert preset.request_limit == 25
    assert preset.total_tokens_limit == 64000
