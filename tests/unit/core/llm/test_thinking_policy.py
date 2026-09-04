"""Tests for llm/thinking_policy.py — intent-aware thinking levels.

Covers:
- Declarative table completeness: every ``IntentCategory`` has an explicit
  entry (adding a category forces a thinking-policy decision)
- Table values are valid pydantic-ai ``ThinkingLevel`` literals or ``None``
- Category semantics: extraction/KB → ``"low"``, analysis/reasoning →
  ``"medium"``, creative/chat → ``None`` (omit)
- :func:`resolve_thinking_level`: per-intent resolution, unmapped intent
  (``EMBED``) → ``None``
"""

from __future__ import annotations

import typing
from typing import Literal

from pydantic_ai.settings import ThinkingLevel

from narrare_core.llm.intent_categories import INTENT_CATEGORY_MAP, IntentCategory
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.thinking_policy import (
    INTENT_CATEGORY_THINKING_LEVELS,
    resolve_thinking_level,
)

_VALID_LEVELS: frozenset[str] = frozenset(
    arg
    for union_member in typing.get_args(ThinkingLevel)
    if typing.get_origin(union_member) is Literal
    for arg in typing.get_args(union_member)
)
"""Literal ``ThinkingLevel`` strings, derived from the installed pydantic-ai."""


class TestTableCompleteness:
    """The declarative table stays in sync with the IntentCategory enum."""

    def test_table_covers_every_intent_category(self) -> None:
        assert {c.value for c in IntentCategory} == set(INTENT_CATEGORY_THINKING_LEVELS)

    def test_table_values_are_valid_thinking_levels_or_none(self) -> None:
        for value in INTENT_CATEGORY_THINKING_LEVELS.values():
            assert value is None or value in _VALID_LEVELS


class TestCategorySemantics:
    """Structured extraction is capped low; judgment work gets medium;
    creative/conversational work omits the key entirely."""

    def test_extraction_and_kb_categories_resolve_low(self) -> None:
        assert INTENT_CATEGORY_THINKING_LEVELS[IntentCategory.EXTRACTION.value] == "low"
        assert INTENT_CATEGORY_THINKING_LEVELS[IntentCategory.KB.value] == "low"

    def test_analysis_research_planning_assist_resolve_medium(self) -> None:
        for category in (
            IntentCategory.ANALYSIS,
            IntentCategory.RESEARCH,
            IntentCategory.PLANNING,
            IntentCategory.AI_ASSIST,
        ):
            assert INTENT_CATEGORY_THINKING_LEVELS[category.value] == "medium"

    def test_writing_generation_chat_categories_omit_thinking(self) -> None:
        for category in (IntentCategory.WRITING, IntentCategory.GENERATION, IntentCategory.CHAT):
            assert INTENT_CATEGORY_THINKING_LEVELS[category.value] is None


class TestResolveThinkingLevel:
    """Per-intent resolution through the category table."""

    def test_kb_extract_resolves_low(self) -> None:
        assert resolve_thinking_level(LLMIntent.KB_EXTRACT) == "low"

    def test_fact_extract_resolves_low(self) -> None:
        assert resolve_thinking_level(LLMIntent.FACT_EXTRACT) == "low"

    def test_analyse_resolves_medium(self) -> None:
        assert resolve_thinking_level(LLMIntent.ANALYSE) == "medium"

    def test_write_resolves_none(self) -> None:
        assert resolve_thinking_level(LLMIntent.WRITE) is None

    def test_chat_resolves_none(self) -> None:
        assert resolve_thinking_level(LLMIntent.CHAT) is None

    def test_embed_unmapped_intent_resolves_none(self) -> None:
        """``EMBED`` has no category (not routed through the cascade) —
        must resolve to ``None``, never raise."""
        assert resolve_thinking_level(LLMIntent.EMBED) is None

    def test_every_routed_intent_resolves_without_error(self) -> None:
        """Every routed intent resolves through the table — no ``KeyError``,
        every result is a valid level or ``None``."""
        for intent in INTENT_CATEGORY_MAP:
            level = resolve_thinking_level(intent)
            assert level is None or level in _VALID_LEVELS
