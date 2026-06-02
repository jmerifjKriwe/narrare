"""Tests for prompts/composer.py"""

from __future__ import annotations

import pytest

from narrare_core.llm import LLMIntent
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


class FakePromptRegistry:
    """Minimal fake for PromptRegistry — returns programmable resolved prompts."""

    def __init__(self, resolved: ResolvedPrompt | None = None) -> None:
        self._resolved = resolved or _make_resolved()

    async def resolve(
        self,
        *,
        category: str,
        language: str,
        mode: str,
        genre: str | None = None,
        db_content: str | None = None,
    ) -> ResolvedPrompt:
        return self._resolved


@pytest.fixture
def fake_registry() -> FakePromptRegistry:
    return FakePromptRegistry()


@pytest.fixture
def composer(fake_registry: FakePromptRegistry) -> PromptComposer:
    return PromptComposer(fake_registry)  # type: ignore[arg-type]


class TestPromptComposerBuild:
    async def test_returns_composed_prompt(self, composer: PromptComposer) -> None:
        ctx = PromptContext(language="en", project_title="My Novel")
        result = await composer.build(LLMIntent.WRITE, ctx)
        assert isinstance(result, ComposedPrompt)
        assert result.system == "System."
        assert result.user == "Hello!"

    async def test_user_prompt_overrides_first_message(self, composer: PromptComposer) -> None:
        ctx = PromptContext(language="en")
        result = await composer.build(LLMIntent.WRITE, ctx, user_prompt="Custom prompt.")
        assert result.user == "Custom prompt."

    async def test_variables_substituted_in_system(self) -> None:
        fake_registry = FakePromptRegistry(_make_resolved(system="Write for {{project_title}}."))
        composer = PromptComposer(fake_registry)  # type: ignore[arg-type]
        ctx = PromptContext(language="en", project_title="Echoes of the Thornwall")
        result = await composer.build(LLMIntent.WRITE, ctx)
        assert "Echoes of the Thornwall" in result.system
