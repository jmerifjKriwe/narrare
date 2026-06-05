"""Tests for generation intents, category mapping, and composer routing.

Covers tasks 2.1-2.5 from generation-prompt-memory-foundation:
- LLMIntent generation members (GENERATE, NAME_GENERATE, TITLE_GENERATE)
- IntentCategory.GENERATION
- INTENT_CATEGORY_MAP entries
- PromptComposer _INTENT_TO_CATEGORY and _INTENT_TO_MODE mappings
"""

from __future__ import annotations

from narrare_core.llm import LLMIntent
from narrare_core.llm.intent_categories import INTENT_CATEGORY_MAP, IntentCategory
from narrare_core.prompts.routes import (
    _INTENT_TO_CATEGORY,
    _INTENT_TO_MODE,
    _NON_ROUTEABLE_INTENTS,
)


class TestGenerationLLMIntents:
    """Task 2.1: Generation intents exist in LLMIntent enum."""

    def test_generate_exists(self) -> None:
        assert hasattr(LLMIntent, "GENERATE")
        assert LLMIntent.GENERATE == "generate"

    def test_name_generate_exists(self) -> None:
        assert hasattr(LLMIntent, "NAME_GENERATE")
        assert LLMIntent.NAME_GENERATE == "name_generate"

    def test_title_generate_exists(self) -> None:
        assert hasattr(LLMIntent, "TITLE_GENERATE")
        assert LLMIntent.TITLE_GENERATE == "title_generate"


class TestGenerationCategory:
    """Task 2.2: IntentCategory.GENERATION and INTENT_CATEGORY_MAP."""

    def test_generation_category_exists(self) -> None:
        assert hasattr(IntentCategory, "GENERATION")
        assert IntentCategory.GENERATION == "generation"

    def test_generate_maps_to_generation(self) -> None:
        assert INTENT_CATEGORY_MAP[LLMIntent.GENERATE] == IntentCategory.GENERATION

    def test_name_generate_maps_to_generation(self) -> None:
        assert INTENT_CATEGORY_MAP[LLMIntent.NAME_GENERATE] == IntentCategory.GENERATION

    def test_title_generate_maps_to_generation(self) -> None:
        assert INTENT_CATEGORY_MAP[LLMIntent.TITLE_GENERATE] == IntentCategory.GENERATION


class TestComposerCategoryMapping:
    """Task 2.3: _INTENT_TO_CATEGORY in PromptComposer."""

    def test_generate_category(self) -> None:
        assert LLMIntent.GENERATE in _NON_ROUTEABLE_INTENTS

    def test_name_generate_category(self) -> None:
        assert _INTENT_TO_CATEGORY[LLMIntent.NAME_GENERATE] == "generation"

    def test_title_generate_category(self) -> None:
        assert LLMIntent.TITLE_GENERATE in _NON_ROUTEABLE_INTENTS


class TestComposerModeMapping:
    """Task 2.4: _INTENT_TO_MODE in PromptComposer."""

    def test_generate_mode(self) -> None:
        assert LLMIntent.GENERATE not in _INTENT_TO_MODE

    def test_name_generate_mode(self) -> None:
        assert _INTENT_TO_MODE[LLMIntent.NAME_GENERATE] == "names"

    def test_title_generate_mode(self) -> None:
        assert LLMIntent.TITLE_GENERATE not in _INTENT_TO_MODE


class TestGenerationIntentRoutingConsistency:
    """Cross-check: every generation intent is fully routed."""

    def test_all_generation_intents_have_category_map(self) -> None:
        """Every generation intent must appear in INTENT_CATEGORY_MAP."""
        for intent in (LLMIntent.GENERATE, LLMIntent.NAME_GENERATE, LLMIntent.TITLE_GENERATE):
            assert intent in INTENT_CATEGORY_MAP

    def test_all_generation_intents_have_prompt_route_decision(self) -> None:
        """Every generation intent has a route or explicit non-routeable decision."""
        for intent in (LLMIntent.GENERATE, LLMIntent.NAME_GENERATE, LLMIntent.TITLE_GENERATE):
            assert intent in _INTENT_TO_CATEGORY or intent in _NON_ROUTEABLE_INTENTS

    def test_all_routeable_generation_intents_have_composer_mode(self) -> None:
        """Routeable generation intents must have a bundled mode."""
        assert LLMIntent.NAME_GENERATE in _INTENT_TO_MODE
