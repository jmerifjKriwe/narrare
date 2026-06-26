"""Tests for ANAL-004 / ADR-021 — ANALYSE pov and readability route resolution.

Verifies that ``resolve_prompt_route`` correctly resolves the pov and
readability context modes for the ANALYSE intent, and that both templates
are loadable via the PromptRegistry cascade. Also re-verifies the existing
review and beta_reader routes to guard against regression.

See test_routes_coreference.py for the multi-mode pattern reference.
"""

from __future__ import annotations

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.route_table import ROUTE_CONFIGS
from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.shared.errors import PromptRouteNotConfiguredError


class TestAnalyseRouteTablePovReadability:
    """ANAL-004 / ADR-021 — ANALYSE pov and readability are governed routes."""

    def test_analyse_default_mode_is_review(self) -> None:
        """Default resolution (no context_mode) returns review."""
        route = resolve_prompt_route(LLMIntent.ANALYSE)
        assert route.category == "analysis"
        assert route.mode == "review"

    def test_analyse_pov_is_routeable(self) -> None:
        """pov context_mode resolves to the pov template."""
        route = resolve_prompt_route(LLMIntent.ANALYSE, context_mode="pov")
        assert route.category == "analysis"
        assert route.mode == "pov"

    def test_analyse_readability_is_routeable(self) -> None:
        """readability context_mode resolves to the readability template."""
        route = resolve_prompt_route(LLMIntent.ANALYSE, context_mode="readability")
        assert route.category == "analysis"
        assert route.mode == "readability"

    def test_analyse_review_is_routeable(self) -> None:
        """review context_mode resolves correctly (regression guard)."""
        route = resolve_prompt_route(LLMIntent.ANALYSE, context_mode="review")
        assert route.category == "analysis"
        assert route.mode == "review"

    def test_analyse_rejects_ungoverned_mode(self) -> None:
        """An unregistered context_mode raises PromptRouteNotConfiguredError."""
        with pytest.raises(PromptRouteNotConfiguredError):
            resolve_prompt_route(LLMIntent.ANALYSE, context_mode="not_a_real_mode")

    def test_analyse_allowed_context_modes_include_all(self) -> None:
        """allowed_context_modes contains review, coreference, pov, readability."""
        modes = ROUTE_CONFIGS[LLMIntent.ANALYSE].allowed_context_modes
        assert {"review", "coreference", "pov", "readability"} <= set(modes)


class TestBetaReaderRouteRegression:
    """BETA_READ route still resolves (regression guard)."""

    def test_beta_read_default_mode_is_beta_reader(self) -> None:
        route = resolve_prompt_route(LLMIntent.BETA_READ)
        assert route.category == "analysis"
        assert route.mode == "beta_reader"

    def test_beta_read_beta_reader_mode_is_routeable(self) -> None:
        route = resolve_prompt_route(LLMIntent.BETA_READ, context_mode="beta_reader")
        assert route.category == "analysis"
        assert route.mode == "beta_reader"


class TestPovTemplateLoadable:
    """The pov template exists and resolves via the cascade."""

    @pytest.fixture
    def registry(self) -> PromptRegistry:
        """Real PromptRegistry resolving against the bundled templates."""
        return PromptRegistry()

    @pytest.mark.asyncio
    async def test_template_resolves_from_bundle(self, registry: PromptRegistry) -> None:
        result = await registry.resolve(category="analysis", language="en", mode="pov")
        assert result.source == "bundled"
        assert result.category == "analysis"
        assert result.language == "en"
        assert result.mode == "pov"
        assert result.system_prompt.strip(), "Empty system prompt for analysis/pov"

    @pytest.mark.asyncio
    async def test_template_frontmatter_matches_category(self, registry: PromptRegistry) -> None:
        """ADR-049 A4: frontmatter prompt_type == category."""
        result = await registry.resolve(category="analysis", language="en", mode="pov")
        assert str(result.metadata.get("prompt_type")) == "analysis"
        assert str(result.metadata.get("prompt_language")) == "en"

    @pytest.mark.asyncio
    async def test_template_has_output_format_section(self, registry: PromptRegistry) -> None:
        """Prompt-structure validator requires an Output Format section."""
        result = await registry.resolve(category="analysis", language="en", mode="pov")
        assert "output format" in result.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_template_covers_pov_violation_types(self, registry: PromptRegistry) -> None:
        """The pov template must mention all four violation categories."""
        result = await registry.resolve(category="analysis", language="en", mode="pov")
        lowered = result.system_prompt.lower()
        assert "head-hop" in lowered or "head_hop" in lowered
        assert "knowledge leak" in lowered or "knowledge_leak" in lowered
        assert "emotional leak" in lowered or "emotional_leak" in lowered
        assert "physical impossibility" in lowered or "physical_impossibility" in lowered


class TestReadabilityTemplateLoadable:
    """The readability template exists and resolves via the cascade."""

    @pytest.fixture
    def registry(self) -> PromptRegistry:
        """Real PromptRegistry resolving against the bundled templates."""
        return PromptRegistry()

    @pytest.mark.asyncio
    async def test_template_resolves_from_bundle(self, registry: PromptRegistry) -> None:
        result = await registry.resolve(category="analysis", language="en", mode="readability")
        assert result.source == "bundled"
        assert result.category == "analysis"
        assert result.language == "en"
        assert result.mode == "readability"
        assert result.system_prompt.strip(), "Empty system prompt for analysis/readability"

    @pytest.mark.asyncio
    async def test_template_frontmatter_matches_category(self, registry: PromptRegistry) -> None:
        """ADR-049 A4: frontmatter prompt_type == category."""
        result = await registry.resolve(category="analysis", language="en", mode="readability")
        assert str(result.metadata.get("prompt_type")) == "analysis"
        assert str(result.metadata.get("prompt_language")) == "en"

    @pytest.mark.asyncio
    async def test_template_has_output_format_section(self, registry: PromptRegistry) -> None:
        """Prompt-structure validator requires an Output Format section."""
        result = await registry.resolve(category="analysis", language="en", mode="readability")
        assert "output format" in result.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_template_preserves_author_voice_directive(
        self, registry: PromptRegistry
    ) -> None:
        """The readability template must instruct preserving the author's voice."""
        result = await registry.resolve(category="analysis", language="en", mode="readability")
        lowered = result.system_prompt.lower()
        assert "voice" in lowered
        assert "preserve" in lowered
