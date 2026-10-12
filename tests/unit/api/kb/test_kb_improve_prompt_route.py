"""Audit B06 regression — KB improve prompt resolves to kb/en/improve.

``KBImproveAnalyzer._build_prompt_context`` set ``mode="kb_improve"`` (the
intent VALUE). ``resolve_prompt_route`` treats a non-empty context mode as
the template mode, so the composer looked up ``kb/en/kb_improve`` — which
does not exist — and the endpoint answered 400 PROMPT_NOT_FOUND. The fix
defers to the route-table default (``kb/en/improve``) via ``mode=""`` and
feeds the template's remaining declared slots from the analyzer's deps.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.routes import resolve_prompt_route


def _make_analyzer() -> Any:
    """Minimal analyzer — only the pure context builder is exercised."""
    from narrare._app.dependencies_services import StaticModelResolution
    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare_core.llm.model_config import ResolvedModelConfig
    from narrare_core.llm.model_routing import ResolvedModel

    config = ResolvedModelConfig(provider_name="test", model_id="test-model")
    return KBImproveAnalyzer(
        registry=cast("Any", AsyncMock()),
        model_resolution=StaticModelResolution(ResolvedModel(config=config)),
        kb_context_provider=cast("Any", AsyncMock()),
        prompt_composer=cast("Any", AsyncMock()),
        kb_repo=cast("Any", AsyncMock()),
        rel_repo=cast("Any", AsyncMock()),
    )


class TestKBImprovePromptRoute:
    def test_context_mode_defers_to_route_table_default(self) -> None:
        ctx = _make_analyzer()._build_prompt_context("character", {"name": "Alice"})
        route = resolve_prompt_route(LLMIntent.KB_IMPROVE, ctx.mode)
        assert (route.category, route.mode) == ("kb", "improve")

    @pytest.mark.asyncio
    async def test_real_cascade_composes_bundled_improve_template(self) -> None:
        """End-to-end compose over the real registry + bundled templates.

        Red today: registry lookup fails for ``kb/en/kb_improve``; green
        after the fix (template found, all declared variables supplied).
        """
        analyzer = _make_analyzer()
        ctx = analyzer._build_prompt_context(
            "character",
            {"name": "Alice"},
            template_structure="name, summary",
            existing_relationships="- Alice → ally → Bob",
            world_context="- Alice (character): a brave hero",
        )
        composer = PromptComposer(PromptRegistry())
        composed = await composer.build(LLMIntent.KB_IMPROVE, ctx)
        assert "Knowledge Base improvement analyst" in composed.system
        assert "Alice" in composed.system
        assert "- Alice → ally → Bob" in composed.system
