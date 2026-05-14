"""Tests for llm/intents.py — IntentCategory mapping and ResolvedModelConfig."""

from __future__ import annotations

import pytest

from narrare_core.llm.intents import (
    INTENT_CATEGORY_MAP,
    IntentCategory,
    LLMIntent,
    ResolvedModelConfig,
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
        assert config.max_tokens == 2000
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
