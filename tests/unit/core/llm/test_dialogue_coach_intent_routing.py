"""Tests for the real (Phase 4) DIALOGUE_COACH routing entries.

Phase 1 Task 5 added DIALOGUE_COACH as an enum member with stub category
(ANALYSIS) + stub profile (long_texts). Phase 4 Task 7 replaces the stubs
with the real ai_assist category + dialogue_coach route entries.

See: ADR-069 Decision 5 (new intent + new category),
     CONSTRAINTS.md RULE-22 (route registration).
"""

from __future__ import annotations

from narrare_core.llm.intent_categories import (
    _INTENT_PROFILE_DEFAULTS,
    INTENT_CATEGORY_MAP,
    IntentCategory,
)
from narrare_core.llm.intent_profiles import INTENT_PROFILES
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.route_table import (
    INTENT_TO_CATEGORY,
    INTENT_TO_MODE,
    NON_ROUTEABLE_INTENTS,
    ROUTE_CONFIGS,
)


class TestIntentCategoryAIAssist:
    """IntentCategory.AI_ASSIST exists and is distinct from ANALYSIS."""

    def test_enum_value(self) -> None:
        assert IntentCategory.AI_ASSIST == "ai_assist"

    def test_is_distinct_from_analysis(self) -> None:
        assert IntentCategory.AI_ASSIST is not IntentCategory.ANALYSIS
        assert IntentCategory.AI_ASSIST is not IntentCategory.WRITING


class TestDialogueCoachCategoryMap:
    """INTENT_CATEGORY_MAP has the REAL ai_assist value (not the stub)."""

    def test_dialogue_coach_is_ai_assist(self) -> None:
        """Phase 4 replaces the Phase 1 ANALYSIS stub."""
        assert INTENT_CATEGORY_MAP[LLMIntent.DIALOGUE_COACH] == IntentCategory.AI_ASSIST

    def test_dialogue_coach_is_not_analysis(self) -> None:
        """Regression guard — the stub value MUST NOT leak back."""
        assert INTENT_CATEGORY_MAP[LLMIntent.DIALOGUE_COACH] != IntentCategory.ANALYSIS


class TestDialogueCoachProfileDefaults:
    """_INTENT_PROFILE_DEFAULTS entry exists (value unchanged from stub)."""

    def test_long_texts_profile(self) -> None:
        assert _INTENT_PROFILE_DEFAULTS[LLMIntent.DIALOGUE_COACH] == "long_texts"


class TestDialogueCoachIntentProfiles:
    """INTENT_PROFILES entry exists with reasoning tier."""

    def test_profile_values(self) -> None:
        profile = INTENT_PROFILES[LLMIntent.DIALOGUE_COACH]
        assert profile.output_profile == "long_texts"
        assert profile.capability_tier == "reasoning"
        assert "Dialogue" in profile.description or "dialogue" in profile.description


class TestDialogueCoachRouteTable:
    """route_table.py has the three required DIALOGUE_COACH entries."""

    def test_intent_to_category(self) -> None:
        assert INTENT_TO_CATEGORY[LLMIntent.DIALOGUE_COACH] == "ai_assist"

    def test_intent_to_mode(self) -> None:
        assert INTENT_TO_MODE[LLMIntent.DIALOGUE_COACH] == "dialogue_coach"

    def test_route_config_exists(self) -> None:
        config = ROUTE_CONFIGS[LLMIntent.DIALOGUE_COACH]
        assert config.category == "ai_assist"
        # NOTE: PromptRouteConfig field is ``default_mode`` (plan-bug #13 — the
        # task brief's verbatim test used ``config.mode`` which does not exist
        # on the slots dataclass and would raise AttributeError).
        assert config.default_mode == "dialogue_coach"

    def test_route_config_optional_variables_include_adaptive(self) -> None:
        """Adaptive variables are declared optional (RULE-22 coherence)."""
        config = ROUTE_CONFIGS[LLMIntent.DIALOGUE_COACH]
        assert "user_preferences" in config.optional_variables
        assert "style_constraints" in config.optional_variables
        assert "avoidance_patterns" in config.optional_variables
        assert "character_voice_profiles" in config.optional_variables
        assert "mode" in config.optional_variables
        assert "characters" in config.optional_variables
        assert "text_to_analyze" in config.optional_variables

    def test_route_config_allowed_context_modes(self) -> None:
        config = ROUTE_CONFIGS[LLMIntent.DIALOGUE_COACH]
        assert "dialogue_coach" in config.allowed_context_modes

    def test_dialogue_coach_is_routeable(self) -> None:
        """DIALOGUE_COACH MUST NOT be in NON_ROUTEABLE_INTENTS."""
        assert LLMIntent.DIALOGUE_COACH not in NON_ROUTEABLE_INTENTS
