"""Tests for SUGGEST intent route resolution — inline_suggest and story_suggest.

Verifies that ``resolve_prompt_route`` correctly resolves both context modes
for the SUGGEST intent (WRITE-009 Writer's Unblock), and that the story_suggest
template is loadable via the PromptRegistry cascade.

See test_routes_debt_migration.py for the multi-mode pattern reference.
"""

from __future__ import annotations

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.route_table import ROUTE_CONFIGS
from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.shared.errors import PromptRouteNotConfiguredError


class TestSuggestRouteTableContextModes:
    """WRITE-009 — SUGGEST context-modes are governed routes."""

    def test_suggest_default_mode_is_inline_suggest(self) -> None:
        """Default resolution (no context_mode) returns inline_suggest."""
        route = resolve_prompt_route(LLMIntent.SUGGEST)
        assert route.category == "writing"
        assert route.mode == "inline_suggest"

    def test_suggest_inline_suggest_is_routeable(self) -> None:
        """inline_suggest context_mode resolves correctly."""
        route = resolve_prompt_route(LLMIntent.SUGGEST, context_mode="inline_suggest")
        assert route.category == "writing"
        assert route.mode == "inline_suggest"

    def test_suggest_story_suggest_is_routeable(self) -> None:
        """story_suggest context_mode resolves to the story_suggest template."""
        route = resolve_prompt_route(LLMIntent.SUGGEST, context_mode="story_suggest")
        assert route.category == "writing"
        assert route.mode == "story_suggest"

    def test_suggest_rejects_ungoverned_mode(self) -> None:
        """An unregistered context_mode raises PromptRouteNotConfiguredError."""
        with pytest.raises(PromptRouteNotConfiguredError):
            resolve_prompt_route(LLMIntent.SUGGEST, context_mode="not_a_real_mode")

    def test_suggest_allowed_context_modes_include_both(self) -> None:
        """allowed_context_modes contains both inline_suggest and story_suggest."""
        modes = ROUTE_CONFIGS[LLMIntent.SUGGEST].allowed_context_modes
        assert {"inline_suggest", "story_suggest"} <= set(modes)

    def test_suggest_no_intent_level_required_variables(self) -> None:
        """WRITE-009: required_variables removed at intent level (context-mode-dependent)."""
        config = ROUTE_CONFIGS[LLMIntent.SUGGEST]
        assert config.required_variables == frozenset()


class TestStorySuggestTemplateLoadable:
    """The story_suggest template exists and resolves via the cascade."""

    @pytest.fixture
    def registry(self) -> PromptRegistry:
        """Real PromptRegistry resolving against the bundled templates."""
        return PromptRegistry()

    @pytest.mark.asyncio
    async def test_template_resolves_from_bundle(self, registry: PromptRegistry) -> None:
        result = await registry.resolve(category="writing", language="en", mode="story_suggest")
        assert result.source == "bundled"
        assert result.category == "writing"
        assert result.language == "en"
        assert result.mode == "story_suggest"
        assert result.system_prompt.strip(), "Empty system prompt for writing/story_suggest"

    @pytest.mark.asyncio
    async def test_template_frontmatter_matches_category(self, registry: PromptRegistry) -> None:
        """ADR-049 A4: frontmatter prompt_type == category."""
        result = await registry.resolve(category="writing", language="en", mode="story_suggest")
        assert str(result.metadata.get("prompt_type")) == "writing"
        assert str(result.metadata.get("prompt_language")) == "en"

    @pytest.mark.asyncio
    async def test_template_has_output_format_section(self, registry: PromptRegistry) -> None:
        """Prompt-structure validator requires an Output Format section."""
        result = await registry.resolve(category="writing", language="en", mode="story_suggest")
        assert "output format" in result.system_prompt.lower()
