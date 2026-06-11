"""Tests for culture injection in PromptComposer.build().

Verifies that:
- {{culture_guidelines}} placeholder is replaced with resolved culture content
- {{culture_guidelines}} is replaced with empty string when no culture specified
- No substitution happens when prompt lacks the placeholder
"""

from __future__ import annotations

from typing import Any, cast

from narrare_core.llm import LLMIntent
from narrare_core.prompts.composer import PromptComposer
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
    """Minimal fake for PromptRegistry with configurable culture resolution."""

    def __init__(
        self,
        resolved: ResolvedPrompt | None = None,
        culture_content: str = "",
    ) -> None:
        self._resolved = resolved or _make_resolved()
        self._culture_content = culture_content
        self.last_name_style: str | None = None
        self.last_category: str | None = None
        self.last_language: str | None = None

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

    async def resolve_name_style(
        self,
        *,
        category: str,
        language: str,
        style_id: str,
    ) -> str:
        self.last_name_style = style_id
        self.last_category = category
        self.last_language = language
        return self._culture_content


class TestCultureInjection:
    """Task 7.6: Culture injection tests."""

    async def test_culture_placeholder_replaced_with_resolved_content(self) -> None:
        """When prompt contains {{culture_guidelines}} and context.extra["name_style"]
        is set: placeholder replaced with resolved content."""
        culture_text = "## German Literary Traditions\n- Follow Schiller's dramatic structure"
        registry = FakePromptRegistry(
            resolved=_make_resolved(system="Write a chapter. {{culture_guidelines}}\nEnd."),
            culture_content=culture_text,
        )
        composer = PromptComposer(cast("Any", registry))

        ctx = PromptContext(language="de", extra={"name_style": "german_literary"})
        result = await composer.build(LLMIntent.WRITE, ctx)

        assert "German Literary Traditions" in result.system
        assert "{{culture_guidelines}}" not in result.system
        assert "Write a chapter." in result.system
        assert "End." in result.system

    async def test_culture_placeholder_replaced_with_empty_when_no_style(self) -> None:
        """When prompt contains {{culture_guidelines}} and no name_style specified:
        placeholder replaced with empty string."""
        registry = FakePromptRegistry(
            resolved=_make_resolved(system="Write. {{culture_guidelines}}\nDone."),
        )
        composer = PromptComposer(cast("Any", registry))

        ctx = PromptContext(language="en")
        result = await composer.build(LLMIntent.WRITE, ctx)

        assert "{{culture_guidelines}}" not in result.system
        assert result.system == "Write. \nDone."

    async def test_no_substitution_when_placeholder_absent(self) -> None:
        """When prompt does NOT contain {{culture_guidelines}}: no substitution
        happens."""
        registry = FakePromptRegistry(
            resolved=_make_resolved(system="Write a chapter."),
        )
        composer = PromptComposer(cast("Any", registry))

        ctx = PromptContext(language="en", extra={"name_style": "german_literary"})
        result = await composer.build(LLMIntent.WRITE, ctx)

        # resolve_name_style should NOT have been called
        assert registry.last_name_style is None
        assert result.system == "Write a chapter."

    async def test_culture_resolved_with_correct_parameters(self) -> None:
        """Verify resolve_name_style receives the correct category, language,
        and name_style."""
        registry = FakePromptRegistry(
            resolved=_make_resolved(system="Write. {{culture_guidelines}}"),
            culture_content="French style.",
        )
        composer = PromptComposer(cast("Any", registry))

        ctx = PromptContext(language="fr", extra={"name_style": "french_existential"})
        await composer.build(LLMIntent.WRITE, ctx)

        assert registry.last_name_style == "french_existential"
        assert registry.last_language == "fr"
        assert registry.last_category == "writing"
