"""Tests for intent→profile mapping completeness and correctness.

Ensures every routeable LLMIntent has an explicit output token profile,
preventing silent fallback to arbitrary defaults (FIND-004).

Also validates the IntentProfile suitability matrix (CR-08 §2.2) —
capability tiers and output profiles per intent.
"""

from __future__ import annotations

import pytest

from narrare_core.llm.intent_categories import (
    INTENT_CATEGORY_MAP,
    get_default_profile_for_intent,
)
from narrare_core.llm.intent_profiles import (
    INTENT_PROFILES,
    VALID_CAPABILITY_TIERS,
    VALID_OUTPUT_PROFILES,
    get_intent_profile,
)
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_config import PROFILE_OUTPUT_LIMITS


class TestProfileCompleteness:
    """Every routeable intent MUST have a profile mapping."""

    @pytest.fixture(params=list(LLMIntent))
    def intent(self, request: pytest.FixtureRequest) -> LLMIntent:
        return request.param

    def test_all_routeable_intents_have_profile(self, intent: LLMIntent) -> None:
        """Every intent in INTENT_CATEGORY_MAP must have a profile."""
        if intent == LLMIntent.EMBED:
            pytest.skip("EMBED is not routeable through model routing")
        assert intent in INTENT_CATEGORY_MAP, f"{intent} not in INTENT_CATEGORY_MAP"
        profile = get_default_profile_for_intent(intent)
        assert profile is not None, (
            f"Intent {intent.value!r} has no output token profile mapping. "
            f"Add it to _INTENT_PROFILE_DEFAULTS in intent_categories.py"
        )

    def test_all_profiles_reference_valid_profile_keys(self) -> None:
        """Every profile name in _INTENT_PROFILE_DEFAULTS must exist in PROFILE_OUTPUT_LIMITS."""
        for intent in LLMIntent:
            profile = get_default_profile_for_intent(intent)
            if profile is None:
                continue
            assert profile in PROFILE_OUTPUT_LIMITS, (
                f"Intent {intent.value!r} references unknown profile {profile!r}"
            )


class TestProfileValues:
    """Profile values must be ordered and sensible."""

    def test_quick_is_smallest(self) -> None:
        assert PROFILE_OUTPUT_LIMITS["quick"] < PROFILE_OUTPUT_LIMITS["balanced"]

    def test_balanced_less_than_long_texts(self) -> None:
        assert PROFILE_OUTPUT_LIMITS["balanced"] < PROFILE_OUTPUT_LIMITS["long_texts"]

    def test_long_texts_not_greater_than_comprehensive(self) -> None:
        # Non-strict since the raises (8000 → 16000, then 16000 → 32000 for
        # the ch-11 benchmark finding) kept the ladder collapsed: long_texts
        # equals comprehensive. Strict separation would require a further
        # comprehensive raise (policy decision, out of scope here).
        assert PROFILE_OUTPUT_LIMITS["long_texts"] <= PROFILE_OUTPUT_LIMITS["comprehensive"]

    def test_comprehensive_profile_exists(self) -> None:
        assert "comprehensive" in PROFILE_OUTPUT_LIMITS
        assert PROFILE_OUTPUT_LIMITS["comprehensive"] == 32000


class TestSpecificIntentProfiles:
    """Verify intent-specific profile assignments."""

    @pytest.mark.parametrize(
        ("intent", "expected_profile"),
        [
            (LLMIntent.WRITE, "long_texts"),
            (LLMIntent.EXTEND, "long_texts"),
            (LLMIntent.REWRITE, "long_texts"),
            (LLMIntent.CO_AUTHOR, "balanced"),
            (LLMIntent.CONSISTENCY, "comprehensive"),
            (LLMIntent.BETA_READ, "long_texts"),
            (LLMIntent.NAME_GENERATE, "quick"),
            (LLMIntent.TITLE_GENERATE, "quick"),
            (LLMIntent.SENTIMENT, "quick"),
            (LLMIntent.VOICE, "balanced"),
            (LLMIntent.CHAT, "balanced"),
            (LLMIntent.RESEARCH, "long_texts"),
            (LLMIntent.KB_EXTRACT, "long_texts"),
            (LLMIntent.KB_WORLDBUILD, "long_texts"),
            (LLMIntent.PLAN, "long_texts"),
            (LLMIntent.SUMMARIZE, "balanced"),
        ],
    )
    def test_intent_profile(self, intent: LLMIntent, expected_profile: str) -> None:
        assert get_default_profile_for_intent(intent) == expected_profile

    def test_embed_has_no_profile(self) -> None:
        """EMBED is not routeable and should have no profile."""
        assert get_default_profile_for_intent(LLMIntent.EMBED) is None


class TestProfileIsPublic:
    """PROFILE_OUTPUT_LIMITS must be public (no underscore prefix)."""

    def test_profile_output_limits_is_importable(self) -> None:
        from narrare_core.llm.model_config import PROFILE_OUTPUT_LIMITS

        assert isinstance(PROFILE_OUTPUT_LIMITS, dict)
        assert len(PROFILE_OUTPUT_LIMITS) >= 4


# ------------------------------------------------------------------
# CR-08 §2.2 — Intent Suitability Matrix (capability tiers)
# ------------------------------------------------------------------


class TestIntentProfileMapping:
    """Every LLMIntent must have an IntentProfile entry with valid values."""

    def test_all_intents_have_profiles(self) -> None:
        """Every enum member must appear in INTENT_PROFILES."""
        for intent in LLMIntent:
            assert intent in INTENT_PROFILES, f"Missing profile for {intent}"

    def test_output_profiles_are_valid(self) -> None:
        for intent, profile in INTENT_PROFILES.items():
            assert profile.output_profile in VALID_OUTPUT_PROFILES, (
                f"{intent}: invalid output_profile '{profile.output_profile}'"
            )

    def test_capability_tiers_are_valid(self) -> None:
        for intent, profile in INTENT_PROFILES.items():
            assert profile.capability_tier in VALID_CAPABILITY_TIERS, (
                f"{intent}: invalid capability_tier '{profile.capability_tier}'"
            )

    def test_descriptions_are_non_empty(self) -> None:
        for intent, profile in INTENT_PROFILES.items():
            assert len(profile.description) > 0, f"{intent}: description is empty"


class TestGetIntentProfile:
    """get_intent_profile returns correct profiles and falls back safely."""

    def test_returns_entry_for_known_intent(self) -> None:
        profile = get_intent_profile(LLMIntent.WRITE)
        assert profile.output_profile == "long_texts"
        assert profile.capability_tier == "creative"

    def test_returns_entry_for_embed(self) -> None:
        profile = get_intent_profile(LLMIntent.EMBED)
        assert profile.output_profile == "quick"
        assert profile.capability_tier == "fast"


class TestIntentProfileTiers:
    """Verify semantic grouping — writing→creative, analysis→reasoning, etc."""

    def test_writing_intents_use_creative(self) -> None:
        writing = [LLMIntent.WRITE, LLMIntent.EXTEND, LLMIntent.REWRITE, LLMIntent.CO_AUTHOR]
        for intent in writing:
            assert INTENT_PROFILES[intent].capability_tier == "creative", (
                f"{intent} should use creative tier"
            )

    def test_analysis_intents_use_reasoning(self) -> None:
        analysis = [
            LLMIntent.ANALYSE,
            LLMIntent.CONSISTENCY,
            LLMIntent.BETA_READ,
            LLMIntent.VOICE,
        ]
        for intent in analysis:
            assert INTENT_PROFILES[intent].capability_tier == "reasoning", (
                f"{intent} should use reasoning tier"
            )

    def test_quick_intents_use_fast_tier(self) -> None:
        """Short-output, non-creative intents use the fast tier."""
        quick = [
            LLMIntent.SUGGEST,
            LLMIntent.SENTIMENT,
        ]
        for intent in quick:
            assert INTENT_PROFILES[intent].capability_tier == "fast", (
                f"{intent} should use fast tier"
            )

    def test_kb_intents_mixed_tiers(self) -> None:
        """KB intents use balanced or reasoning — never fast."""
        kb_intents = [
            LLMIntent.KB_CREATE,
            LLMIntent.KB_IMPROVE,
            LLMIntent.KB_EXTRACT,
            LLMIntent.KB_INTERVIEW,
            LLMIntent.KB_SUGGEST,
            LLMIntent.KB_ENHANCE,
            LLMIntent.KB_WORLDBUILD,
            LLMIntent.KB_CONSISTENCY,
        ]
        for intent in kb_intents:
            tier = INTENT_PROFILES[intent].capability_tier
            assert tier in {"balanced", "reasoning", "creative"}, (
                f"{intent} has unexpected tier '{tier}'"
            )
