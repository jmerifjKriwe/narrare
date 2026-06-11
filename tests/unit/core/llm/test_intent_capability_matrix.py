"""Tests for intent→capability-profile mapping (intent_profiles.py).

Validates the advisory IntentProfile matrix: completeness, valid values,
category-based tier patterns, and fallback behaviour.

This tests the *capability tier* dimension added in CR-08 §2.2.
The output token profile dimension is tested in ``test_intent_profiles.py``
(via ``intent_categories._INTENT_PROFILE_DEFAULTS``).
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from narrare_core.llm.intent_profiles import (
    INTENT_PROFILES,
    VALID_CAPABILITY_TIERS,
    VALID_OUTPUT_PROFILES,
    IntentProfile,
    get_intent_profile,
)
from narrare_core.llm.intents import LLMIntent

# ------------------------------------------------------------------
# Completeness — every LLMIntent member has an entry
# ------------------------------------------------------------------


class TestProfileCompleteness:
    """Every LLMIntent member MUST have a profile entry."""

    @pytest.fixture(params=list(LLMIntent))
    def intent(self, request: pytest.FixtureRequest) -> LLMIntent:
        return request.param

    def test_every_intent_has_profile(self, intent: LLMIntent) -> None:
        """All 27 intents are present in INTENT_PROFILES."""
        assert intent in INTENT_PROFILES, (
            f"{intent.value!r} is missing from INTENT_PROFILES. "
            f"Add it to the mapping table in intent_profiles.py."
        )

    def test_no_extra_entries_beyond_enum(self) -> None:
        """INTENT_PROFILES must not contain keys outside LLMIntent."""
        intent_values = set(LLMIntent)
        extra = set(INTENT_PROFILES.keys()) - intent_values
        assert not extra, f"INTENT_PROFILES contains keys not in LLMIntent: {extra}"


# ------------------------------------------------------------------
# Valid values — output_profile and capability_tier are in allowed sets
# ------------------------------------------------------------------


class TestProfileValues:
    """All profile values must be from the defined valid sets."""

    def test_all_output_profiles_are_valid(self) -> None:
        for intent, profile in INTENT_PROFILES.items():
            assert profile.output_profile in VALID_OUTPUT_PROFILES, (
                f"Intent {intent.value!r} has invalid output_profile "
                f"{profile.output_profile!r}. "
                f"Valid: {sorted(VALID_OUTPUT_PROFILES)}"
            )

    def test_all_capability_tiers_are_valid(self) -> None:
        for intent, profile in INTENT_PROFILES.items():
            assert profile.capability_tier in VALID_CAPABILITY_TIERS, (
                f"Intent {intent.value!r} has invalid capability_tier "
                f"{profile.capability_tier!r}. "
                f"Valid: {sorted(VALID_CAPABILITY_TIERS)}"
            )

    def test_all_profiles_have_nonempty_description(self) -> None:
        for intent, profile in INTENT_PROFILES.items():
            assert profile.description.strip(), f"Intent {intent.value!r} has an empty description."


# ------------------------------------------------------------------
# Category-based tier patterns — writing→creative, analysis→reasoning
# ------------------------------------------------------------------


class TestCategoryTierPatterns:
    """Intent categories follow expected capability patterns."""

    @pytest.mark.parametrize(
        "intent",
        [
            LLMIntent.WRITE,
            LLMIntent.EXTEND,
            LLMIntent.REWRITE,
            LLMIntent.CO_AUTHOR,
        ],
        ids=lambda i: i.value,
    )
    def test_writing_intents_use_creative_tier(self, intent: LLMIntent) -> None:
        profile = INTENT_PROFILES[intent]
        assert profile.capability_tier == "creative", (
            f"Writing intent {intent.value!r} should use 'creative' tier, "
            f"got {profile.capability_tier!r}"
        )

    @pytest.mark.parametrize(
        "intent",
        [
            LLMIntent.ANALYSE,
            LLMIntent.CONSISTENCY,
            LLMIntent.BETA_READ,
            LLMIntent.VOICE,
        ],
        ids=lambda i: i.value,
    )
    def test_analysis_intents_use_reasoning_tier(self, intent: LLMIntent) -> None:
        profile = INTENT_PROFILES[intent]
        assert profile.capability_tier == "reasoning", (
            f"Analysis intent {intent.value!r} should use 'reasoning' tier, "
            f"got {profile.capability_tier!r}"
        )

    @pytest.mark.parametrize(
        "intent",
        [
            LLMIntent.KB_IMPROVE,
            LLMIntent.KB_EXTRACT,
            LLMIntent.KB_WORLDBUILD,
            LLMIntent.KB_CONSISTENCY,
        ],
        ids=lambda i: i.value,
    )
    def test_kb_analysis_intents_use_reasoning_tier(self, intent: LLMIntent) -> None:
        profile = INTENT_PROFILES[intent]
        assert profile.capability_tier == "reasoning", (
            f"KB analysis intent {intent.value!r} should use 'reasoning' tier, "
            f"got {profile.capability_tier!r}"
        )

    @pytest.mark.parametrize(
        "intent",
        [
            LLMIntent.SENTIMENT,
            LLMIntent.SUGGEST,
            LLMIntent.SUMMARIZE,
        ],
        ids=lambda i: i.value,
    )
    def test_fast_operation_intents_use_fast_tier(self, intent: LLMIntent) -> None:
        profile = INTENT_PROFILES[intent]
        assert profile.capability_tier == "fast", (
            f"Fast intent {intent.value!r} should use 'fast' tier, got {profile.capability_tier!r}"
        )


# ------------------------------------------------------------------
# Fallback — get_intent_profile returns default for unknown intents
# ------------------------------------------------------------------


class TestGetIntentProfileFallback:
    """get_intent_profile must handle edge cases gracefully."""

    def test_returns_valid_profile_for_known_intent(self) -> None:
        """get_intent_profile returns a proper IntentProfile for known intents."""
        result = get_intent_profile(LLMIntent.WRITE)
        assert isinstance(result, IntentProfile)
        assert result.output_profile in VALID_OUTPUT_PROFILES
        assert result.capability_tier in VALID_CAPABILITY_TIERS

    def test_fallback_profile_has_balanced_values(self) -> None:
        """The fallback profile must be balanced/balanced."""
        # Create a custom LLMIntent-like value that won't be in the dict
        # by testing the .get() path directly
        from narrare_core.llm import intent_profiles

        original = intent_profiles.INTENT_PROFILES.copy()
        # Temporarily empty the dict to force fallback
        intent_profiles.INTENT_PROFILES.clear()
        try:
            result = get_intent_profile(LLMIntent.WRITE)
            assert result.output_profile == "balanced"
            assert result.capability_tier == "balanced"
            assert "Unknown" in result.description
        finally:
            intent_profiles.INTENT_PROFILES.update(original)


# ------------------------------------------------------------------
# IntentProfile dataclass immutability
# ------------------------------------------------------------------


class TestIntentProfileDataclass:
    """IntentProfile is frozen and has slots."""

    def test_frozen_raises_on_attribute_assignment(self) -> None:
        profile = IntentProfile("quick", "fast", "test")
        with pytest.raises(AttributeError):
            cast("Any", profile).output_profile = "balanced"

    def test_has_slots(self) -> None:
        profile = IntentProfile("quick", "fast", "test")
        assert hasattr(profile, "__slots__")

    def test_equality(self) -> None:
        a = IntentProfile("quick", "fast", "test")
        b = IntentProfile("quick", "fast", "test")
        assert a == b

    def test_inequality(self) -> None:
        a = IntentProfile("quick", "fast", "test")
        b = IntentProfile("balanced", "fast", "test")
        assert a != b
