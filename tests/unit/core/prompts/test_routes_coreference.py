"""Tests for ANAL-005 — ANALYSE coreference route resolution.

Verifies that ``resolve_prompt_route`` correctly resolves both context modes
for the ANALYSE intent (review default + coreference), and that the
coreference template is loadable via the PromptRegistry cascade.

See test_routes_story_suggest.py for the multi-mode pattern reference.
"""

from __future__ import annotations

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.route_table import ROUTE_CONFIGS
from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.shared.errors import PromptRouteNotConfiguredError


class TestAnalyseRouteTableContextModes:
    """ANAL-005 — ANALYSE context-modes are governed routes."""

    def test_analyse_default_mode_is_review(self) -> None:
        """Default resolution (no context_mode) returns review."""
        route = resolve_prompt_route(LLMIntent.ANALYSE)
        assert route.category == "analysis"
        assert route.mode == "review"

    def test_analyse_review_is_routeable(self) -> None:
        """review context_mode resolves correctly."""
        route = resolve_prompt_route(LLMIntent.ANALYSE, context_mode="review")
        assert route.category == "analysis"
        assert route.mode == "review"

    def test_analyse_coreference_is_routeable(self) -> None:
        """coreference context_mode resolves to the coreference template."""
        route = resolve_prompt_route(LLMIntent.ANALYSE, context_mode="coreference")
        assert route.category == "analysis"
        assert route.mode == "coreference"

    def test_analyse_rejects_ungoverned_mode(self) -> None:
        """An unregistered context_mode raises PromptRouteNotConfiguredError."""
        with pytest.raises(PromptRouteNotConfiguredError):
            resolve_prompt_route(LLMIntent.ANALYSE, context_mode="not_a_real_mode")

    def test_analyse_allowed_context_modes_include_both(self) -> None:
        """allowed_context_modes contains both review and coreference."""
        modes = ROUTE_CONFIGS[LLMIntent.ANALYSE].allowed_context_modes
        assert {"review", "coreference"} <= set(modes)


class TestCoreferenceTemplateLoadable:
    """The coreference template exists and resolves via the cascade."""

    @pytest.fixture
    def registry(self) -> PromptRegistry:
        """Real PromptRegistry resolving against the bundled templates."""
        return PromptRegistry()

    @pytest.mark.asyncio
    async def test_template_resolves_from_bundle(self, registry: PromptRegistry) -> None:
        result = await registry.resolve(category="analysis", language="en", mode="coreference")
        assert result.source == "bundled"
        assert result.category == "analysis"
        assert result.language == "en"
        assert result.mode == "coreference"
        assert result.system_prompt.strip(), "Empty system prompt for analysis/coreference"

    @pytest.mark.asyncio
    async def test_template_frontmatter_matches_category(self, registry: PromptRegistry) -> None:
        """ADR-049 A4: frontmatter prompt_type == category."""
        result = await registry.resolve(category="analysis", language="en", mode="coreference")
        assert str(result.metadata.get("prompt_type")) == "analysis"
        assert str(result.metadata.get("prompt_language")) == "en"

    @pytest.mark.asyncio
    async def test_template_has_output_format_section(self, registry: PromptRegistry) -> None:
        """Prompt-structure validator requires an Output Format section."""
        result = await registry.resolve(category="analysis", language="en", mode="coreference")
        assert "output format" in result.system_prompt.lower()
