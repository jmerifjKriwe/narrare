"""Tests for ADR-054 — inline-feature-prompt debt migration routes.

Covers the core half of ADR-054 (Step 1: route-table context-modes; Step 2:
the three governed templates). The services themselves are migrated in Step 3
(backend slice) and are out of scope here.

Verifies:
  * ``PLAN`` routes ``character_arc`` / ``timeline_extraction`` to their
    governed templates via ``context_mode``.
  * ``KB_CONSISTENCY`` routes ``merge`` (and still routes ``consistency``) via
    ``context_mode``, and keeps its default mode.
  * The three new templates exist and are loadable by ``PromptRegistry``
    (the single cascade resolver), with valid frontmatter.

See: ``docs/architecture/decisions/ADR-054-inline-feature-prompt-debt-migration.md``
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.route_table import ROUTE_CONFIGS
from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.shared.errors import PromptNotFoundError, PromptRouteNotConfiguredError


class TestADR054RouteTableContextModes:
    """ADR-054 D4/D5 — new context-modes are governed routes."""

    def test_plan_character_arc_is_routeable(self) -> None:
        route = resolve_prompt_route(LLMIntent.PLAN, context_mode="character_arc")
        assert route.category == "planning"
        assert route.mode == "character_arc"

    def test_plan_timeline_extraction_is_routeable(self) -> None:
        route = resolve_prompt_route(LLMIntent.PLAN, context_mode="timeline_extraction")
        assert route.category == "planning"
        assert route.mode == "timeline_extraction"

    def test_kb_consistency_merge_is_routeable(self) -> None:
        route = resolve_prompt_route(LLMIntent.KB_CONSISTENCY, context_mode="merge")
        assert route.category == "kb"
        assert route.mode == "merge"

    def test_kb_consistency_consistency_mode_still_routeable(self) -> None:
        """D5: 'consistency' (the default) is also an explicit context-mode."""
        route = resolve_prompt_route(LLMIntent.KB_CONSISTENCY, context_mode="consistency")
        assert route.category == "kb"
        assert route.mode == "consistency"

    def test_kb_consistency_default_mode_unchanged(self) -> None:
        """Default resolution (no context_mode) still returns 'consistency'."""
        route = resolve_prompt_route(LLMIntent.KB_CONSISTENCY)
        assert route.category == "kb"
        assert route.mode == "consistency"

    def test_plan_rejects_ungoverned_mode(self) -> None:
        with pytest.raises(PromptRouteNotConfiguredError):
            resolve_prompt_route(LLMIntent.PLAN, context_mode="not_a_real_mode")

    def test_plan_allowed_context_modes_include_new_modes(self) -> None:
        modes = ROUTE_CONFIGS[LLMIntent.PLAN].allowed_context_modes
        assert {"character_arc", "timeline_extraction"} <= set(modes)

    def test_kb_consistency_allowed_context_modes_include_merge(self) -> None:
        modes = ROUTE_CONFIGS[LLMIntent.KB_CONSISTENCY].allowed_context_modes
        assert {"consistency", "merge"} <= set(modes)


class TestADR054TemplatesLoadable:
    """The three governed templates exist and resolve via the cascade."""

    # (category, mode) — language is always 'en' for the v1 cut (ADR-054 D6).
    _CASES: ClassVar[list[tuple[str, str]]] = [
        ("planning", "character_arc"),
        ("planning", "timeline_extraction"),
        ("kb", "merge"),
    ]

    @pytest.fixture
    def registry(self) -> PromptRegistry:
        """Real PromptRegistry resolving against the bundled templates."""
        return PromptRegistry()

    @pytest.mark.parametrize(("category", "mode"), _CASES)
    async def test_template_resolves_from_bundle(
        self,
        registry: PromptRegistry,
        category: str,
        mode: str,
    ) -> None:
        result = await registry.resolve(category=category, language="en", mode=mode)
        assert result.source == "bundled"
        assert result.category == category
        assert result.language == "en"
        assert result.mode == mode
        assert result.system_prompt.strip(), f"Empty system prompt for {category}/{mode}"

    @pytest.mark.parametrize(("category", "mode"), _CASES)
    async def test_template_frontmatter_matches_category(
        self,
        registry: PromptRegistry,
        category: str,
        mode: str,
    ) -> None:
        """ADR-049 A4 / ADR-054 D6: frontmatter prompt_type == category."""
        result = await registry.resolve(category=category, language="en", mode=mode)
        assert str(result.metadata.get("prompt_type")) == category
        assert str(result.metadata.get("prompt_language")) == "en"

    @pytest.mark.parametrize(("category", "mode"), _CASES)
    async def test_template_has_output_format_section(
        self,
        registry: PromptRegistry,
        category: str,
        mode: str,
    ) -> None:
        """Prompt-structure validator requires an Output Format section."""
        result = await registry.resolve(category=category, language="en", mode=mode)
        assert "output format" in result.system_prompt.lower()

    async def test_unknown_mode_raises_not_found(self, registry: PromptRegistry) -> None:
        with pytest.raises(PromptNotFoundError):
            await registry.resolve(category="planning", language="en", mode="does_not_exist")
