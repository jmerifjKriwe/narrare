"""Tests for intent→profile mapping completeness and correctness.

Ensures every routeable LLMIntent has an explicit output token profile,
preventing silent fallback to arbitrary defaults (FIND-004).
"""

from __future__ import annotations

import pytest

from narrare_core.llm.intent_categories import (
    INTENT_CATEGORY_MAP,
    get_default_profile_for_intent,
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

    def test_long_texts_less_than_comprehensive(self) -> None:
        assert PROFILE_OUTPUT_LIMITS["long_texts"] < PROFILE_OUTPUT_LIMITS["comprehensive"]

    def test_comprehensive_profile_exists(self) -> None:
        assert "comprehensive" in PROFILE_OUTPUT_LIMITS
        assert PROFILE_OUTPUT_LIMITS["comprehensive"] == 16000


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
