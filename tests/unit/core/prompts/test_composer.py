"""Tests for prompts/composer.py"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import ResolvedPrompt


def _make_resolved(system: str = "System.", first: str | None = "Hello!") -> ResolvedPrompt:
    return ResolvedPrompt(
        system_prompt=system,
        first_message=first,
        source="bundled",
        category="writing",
        language="en",
        mode="new_chapter",
        metadata={},
    )


@pytest.fixture
def mock_registry() -> MagicMock:
    registry = MagicMock()
    registry.resolve = AsyncMock(return_value=_make_resolved())
    return registry


@pytest.fixture
def mock_meta_loader() -> MagicMock:
    loader = MagicMock()
    loader.load = AsyncMock(return_value="")
    return loader


@pytest.fixture
def composer(mock_registry: MagicMock, mock_meta_loader: MagicMock) -> PromptComposer:
    return PromptComposer(mock_registry, mock_meta_loader)


class TestPromptComposerBuild:
    async def test_returns_composed_prompt(self, composer: PromptComposer) -> None:
        ctx = PromptContext(language="en", project_title="My Novel")
        result = await composer.build(LLMIntent.WRITE, ctx)
        assert isinstance(result, ComposedPrompt)
        assert result.system == "System."
        assert result.user == "Hello!"

    async def test_meta_prepended_when_present(
        self,
        mock_registry: MagicMock,
        mock_meta_loader: MagicMock,
    ) -> None:
        mock_meta_loader.load = AsyncMock(return_value="You are a writing assistant.")
        composer = PromptComposer(mock_registry, mock_meta_loader)
        ctx = PromptContext(language="en")
        result = await composer.build(LLMIntent.WRITE, ctx)
        assert result.system.startswith("You are a writing assistant.")
        assert "System." in result.system

    async def test_user_prompt_overrides_first_message(self, composer: PromptComposer) -> None:
        ctx = PromptContext(language="en")
        result = await composer.build(LLMIntent.WRITE, ctx, user_prompt="Custom prompt.")
        assert result.user == "Custom prompt."

    async def test_variables_substituted_in_system(
        self,
        mock_registry: MagicMock,
        mock_meta_loader: MagicMock,
    ) -> None:
        mock_registry.resolve = AsyncMock(
            return_value=_make_resolved(system="Write for {{project_title}}.")
        )
        composer = PromptComposer(mock_registry, mock_meta_loader)
        ctx = PromptContext(language="en", project_title="Echoes of the Thornwall")
        result = await composer.build(LLMIntent.WRITE, ctx)
        assert "Echoes of the Thornwall" in result.system

    async def test_no_meta_when_disabled(
        self,
        mock_registry: MagicMock,
        mock_meta_loader: MagicMock,
    ) -> None:
        mock_meta_loader.load = AsyncMock(return_value="Meta prompt text.")
        composer = PromptComposer(mock_registry, mock_meta_loader, include_meta=False)
        ctx = PromptContext(language="en")
        result = await composer.build(LLMIntent.WRITE, ctx)
        assert "Meta prompt text." not in result.system
