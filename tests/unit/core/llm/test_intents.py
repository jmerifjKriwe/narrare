"""Tests for llm/intents.py — IntentCategory mapping and ResolvedModelConfig."""

from __future__ import annotations

import pytest

from narrare_core.llm.intents import (
    _INTENT_PROFILE_DEFAULTS,
    _PROFILE_OUTPUT_LIMITS,
    INTENT_CATEGORY_MAP,
    IntentCategory,
    LLMIntent,
    ResolvedModelConfig,
    get_default_profile_for_intent,
)


class TestLLMIntent:
    def test_every_routeable_intent_has_category(self) -> None:
        """Every intent except EMBED must map to a category."""
        for intent in LLMIntent:
            if intent == LLMIntent.EMBED:
                continue
            assert intent in INTENT_CATEGORY_MAP, (
                f"LLMIntent.{intent.name} is not in INTENT_CATEGORY_MAP. Add it in llm/intents.py."
            )

    def test_embed_has_no_category(self) -> None:
        """EMBED is intentionally excluded from category mapping."""
        assert LLMIntent.EMBED not in INTENT_CATEGORY_MAP

    def test_all_categories_represented(self) -> None:
        """All 7 categories should have at least one intent."""
        covered = set(INTENT_CATEGORY_MAP.values())
        expected = set(IntentCategory)
        assert covered == expected, (
            f"Missing categories: {expected - covered}. Extra categories: {covered - expected}"
        )


class TestIntentCategoryMap:
    @pytest.mark.parametrize(
        ("intent", "expected_category"),
        [
            # Writing
            (LLMIntent.WRITE, IntentCategory.WRITING),
            (LLMIntent.EXTEND, IntentCategory.WRITING),
            (LLMIntent.REWRITE, IntentCategory.WRITING),
            (LLMIntent.CO_AUTHOR, IntentCategory.WRITING),
            # Analysis
            (LLMIntent.ANALYSE, IntentCategory.ANALYSIS),
            (LLMIntent.SENTIMENT, IntentCategory.ANALYSIS),
            (LLMIntent.CONSISTENCY, IntentCategory.ANALYSIS),
            (LLMIntent.BETA_READ, IntentCategory.ANALYSIS),
            (LLMIntent.VOICE, IntentCategory.ANALYSIS),
            # KB
            (LLMIntent.KB_CREATE, IntentCategory.KB),
            (LLMIntent.KB_IMPROVE, IntentCategory.KB),
            (LLMIntent.KB_EXTRACT, IntentCategory.KB),
            # Planning
            (LLMIntent.PLAN, IntentCategory.PLANNING),
            (LLMIntent.SUMMARIZE, IntentCategory.PLANNING),
            # Extraction
            (LLMIntent.EXTRACT, IntentCategory.EXTRACTION),
            (LLMIntent.SUGGEST, IntentCategory.EXTRACTION),
            # Chat
            (LLMIntent.CHAT, IntentCategory.CHAT),
            # Research
            (LLMIntent.RESEARCH, IntentCategory.RESEARCH),
        ],
    )
    def test_intent_maps_to_correct_category(
        self,
        intent: LLMIntent,
        expected_category: IntentCategory,
    ) -> None:
        assert INTENT_CATEGORY_MAP[intent] == expected_category


class TestResolvedModelConfig:
    def test_creation_with_required_fields(self) -> None:
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
        )
        assert config.provider_name == "anthropic"
        assert config.model_id == "claude-sonnet-4-5-20251020"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.streams is False

    def test_creation_with_all_fields(self) -> None:
        config = ResolvedModelConfig(
            provider_name="openrouter",
            model_id="anthropic/claude-sonnet-4-5",
            temperature=0.9,
            max_tokens=8000,
            streams=True,
        )
        assert config.provider_name == "openrouter"
        assert config.model_id == "anthropic/claude-sonnet-4-5"
        assert config.temperature == 0.9
        assert config.max_tokens == 8000
        assert config.streams is True

    def test_frozen(self) -> None:
        config = ResolvedModelConfig(
            provider_name="anthropic", model_id="claude-sonnet-4-5-20251020"
        )
        with pytest.raises(AttributeError):
            config.provider_name = "openai"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = ResolvedModelConfig(provider_name="anthropic", model_id="claude-sonnet-4-5-20251020")
        b = ResolvedModelConfig(provider_name="anthropic", model_id="claude-sonnet-4-5-20251020")
        assert a == b

    def test_inequality(self) -> None:
        a = ResolvedModelConfig(provider_name="anthropic", model_id="claude-sonnet-4-5-20251020")
        b = ResolvedModelConfig(provider_name="openai", model_id="gpt-4o")
        assert a != b

    # ------------------------------------------------------------------
    # resolve_output_limit
    # ------------------------------------------------------------------

    def test_resolve_output_limit_uses_profile_param(self) -> None:
        """Explicit profile param takes priority."""
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
        )
        assert (
            config.resolve_output_limit(profile="long_texts")
            == _PROFILE_OUTPUT_LIMITS["long_texts"]
        )

    def test_resolve_output_limit_uses_quick_profile(self) -> None:
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
        )
        assert config.resolve_output_limit(profile="quick") == _PROFILE_OUTPUT_LIMITS["quick"]

    def test_resolve_output_limit_falls_back_to_max_tokens(self) -> None:
        """When no profile is known, return max_tokens."""
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
        )
        assert config.resolve_output_limit() == config.max_tokens

    def test_resolve_output_limit_unknown_profile_falls_back(self) -> None:
        """Unknown profile name falls back to max_tokens."""
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
        )
        assert config.resolve_output_limit(profile="nonexistent") == config.max_tokens

    def test_resolve_output_limit_uses_token_limit_profile_attr(self) -> None:
        """Instance-level token_limit_profile is used when no arg given."""
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            token_limit_profile="long_texts",
        )
        assert config.resolve_output_limit() == _PROFILE_OUTPUT_LIMITS["long_texts"]

    def test_resolve_output_limit_profile_param_overrides_attr(self) -> None:
        """Explicit profile param overrides token_limit_profile attr."""
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            token_limit_profile="long_texts",
        )
        assert config.resolve_output_limit(profile="quick") == _PROFILE_OUTPUT_LIMITS["quick"]

    def test_resolve_output_limit_unknown_token_limit_profile_falls_back(self) -> None:
        """Unknown token_limit_profile falls back to max_tokens."""
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            token_limit_profile="bogus",
        )
        assert config.resolve_output_limit() == config.max_tokens


class TestIntentProfileDefaults:
    """Tests for _INTENT_PROFILE_DEFAULTS and get_default_profile_for_intent."""

    def test_beta_read_defaults_to_long_texts(self) -> None:
        """Beta-reader analysis needs higher output limit."""
        assert _INTENT_PROFILE_DEFAULTS[LLMIntent.BETA_READ] == "long_texts"
        assert get_default_profile_for_intent(LLMIntent.BETA_READ) == "long_texts"

    def test_name_generate_defaults_to_quick(self) -> None:
        """Name generation is lightweight — use quick profile."""
        assert _INTENT_PROFILE_DEFAULTS[LLMIntent.NAME_GENERATE] == "quick"
        assert get_default_profile_for_intent(LLMIntent.NAME_GENERATE) == "quick"

    def test_unmapped_intent_returns_none(self) -> None:
        """Intents without explicit defaults return None."""
        assert get_default_profile_for_intent(LLMIntent.WRITE) is None
        assert get_default_profile_for_intent(LLMIntent.CHAT) is None

    def test_all_defaults_reference_valid_profiles(self) -> None:
        """Every profile name in _INTENT_PROFILE_DEFAULTS must exist in _PROFILE_OUTPUT_LIMITS."""
        for intent, profile in _INTENT_PROFILE_DEFAULTS.items():
            assert profile in _PROFILE_OUTPUT_LIMITS, (
                f"Intent {intent.name!r} maps to unknown profile {profile!r}"
            )

    def test_resolver_sets_profile_on_config(self) -> None:
        """ResolvedModelConfig with token_limit_profile resolves correctly."""
        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            token_limit_profile="long_texts",
        )
        assert config.resolve_output_limit() == _PROFILE_OUTPUT_LIMITS["long_texts"]
