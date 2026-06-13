"""Tests for prompts/routes.py — prompt route resolution."""

from __future__ import annotations

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.route_table import ROUTE_CONFIGS
from narrare_core.prompts.route_types import PromptRouteConfig
from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.shared.errors import PromptRouteNotConfiguredError


class TestResolvePromptRoute:
    def test_raises_for_unconfigured_intent(self) -> None:
        """An intent with no config entry raises PromptRouteNotConfiguredError."""
        with pytest.raises(PromptRouteNotConfiguredError, match=LLMIntent.EMBED.value):
            resolve_prompt_route(LLMIntent.EMBED)

    def test_raises_when_default_mode_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An intent with default_mode=None raises PromptRouteNotConfiguredError (line 64)."""
        monkeypatch.setitem(
            ROUTE_CONFIGS,
            LLMIntent.SUMMARIZE,
            PromptRouteConfig(category="analysis", default_mode=None),
        )
        with pytest.raises(
            PromptRouteNotConfiguredError,
            match="No PromptComposer mode mapping",
        ):
            resolve_prompt_route(LLMIntent.SUMMARIZE)
