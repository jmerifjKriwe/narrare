"""Tests for generation intents, category mapping, and composer routing.

Covers tasks 2.1-2.5 from generation-prompt-memory-foundation:
- LLMIntent generation members (GENERATE, NAME_GENERATE, TITLE_GENERATE)
- IntentCategory.GENERATION
- INTENT_CATEGORY_MAP entries
- PromptComposer _INTENT_TO_CATEGORY and _INTENT_TO_MODE mappings
"""

from __future__ import annotations

from narrare_core.llm.intents import INTENT_CATEGORY_MAP, IntentCategory, LLMIntent
from narrare_core.prompts.composer import _INTENT_TO_CATEGORY, _INTENT_TO_MODE


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
        assert _INTENT_TO_CATEGORY[LLMIntent.GENERATE] == "generation"

    def test_name_generate_category(self) -> None:
        assert _INTENT_TO_CATEGORY[LLMIntent.NAME_GENERATE] == "generation"

    def test_title_generate_category(self) -> None:
        assert _INTENT_TO_CATEGORY[LLMIntent.TITLE_GENERATE] == "generation"


class TestComposerModeMapping:
    """Task 2.4: _INTENT_TO_MODE in PromptComposer."""

    def test_generate_mode(self) -> None:
        assert _INTENT_TO_MODE[LLMIntent.GENERATE] == "general"

    def test_name_generate_mode(self) -> None:
        assert _INTENT_TO_MODE[LLMIntent.NAME_GENERATE] == "names"

    def test_title_generate_mode(self) -> None:
        assert _INTENT_TO_MODE[LLMIntent.TITLE_GENERATE] == "titles"


class TestGenerationIntentRoutingConsistency:
    """Cross-check: every generation intent is fully routed."""

    def test_all_generation_intents_have_category_map(self) -> None:
        """Every generation intent must appear in INTENT_CATEGORY_MAP."""
        for intent in (LLMIntent.GENERATE, LLMIntent.NAME_GENERATE, LLMIntent.TITLE_GENERATE):
            assert intent in INTENT_CATEGORY_MAP

    def test_all_generation_intents_have_composer_category(self) -> None:
        """Every generation intent must appear in _INTENT_TO_CATEGORY."""
        for intent in (LLMIntent.GENERATE, LLMIntent.NAME_GENERATE, LLMIntent.TITLE_GENERATE):
            assert intent in _INTENT_TO_CATEGORY

    def test_all_generation_intents_have_composer_mode(self) -> None:
        """Every generation intent must appear in _INTENT_TO_MODE."""
        for intent in (LLMIntent.GENERATE, LLMIntent.NAME_GENERATE, LLMIntent.TITLE_GENERATE):
            assert intent in _INTENT_TO_MODE
