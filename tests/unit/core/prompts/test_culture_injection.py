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


class TestCultureGuidelinesComposerOwnership:
    """§7 regression: ``culture_guidelines`` is owned by the PromptComposer,
    not by a service ``extra`` entry.

    Wave-1 of the §7 closing plan removed the dead
    ``extra["culture_guidelines"] = ""`` entries from four services
    (character_arc, timeline_analysis, timeline_extraction, story_suggest).
    The Composer unconditionally substitutes ``{{culture_guidelines}}`` —
    resolved from ``name_style`` via the registry, else ``""`` (see
    composer.py build()) — regardless of any value a service places in
    ``extra``. These tests lock that contract: the removed entries were pure
    no-ops, and their absence cannot cause a ``PromptVariableError`` or alter
    the composed prompt.

    Placed at the Composer layer because the Composer is the single source
    of truth for ``culture_guidelines``; a property proved once here holds for
    every service that delegates to it (architectural-discipline §1, Root
    Cause First). The four touched services share this one Composer path.
    """

    @staticmethod
    def _registry(culture_content: str = "") -> FakePromptRegistry:
        return FakePromptRegistry(
            resolved=_make_resolved(
                system="Cultural context:\n{{culture_guidelines}}\nDone.",
            ),
            culture_content=culture_content,
        )

    async def test_extra_entry_is_noop_when_name_style_set(self) -> None:
        """With a ``name_style`` the Composer resolves ``{{culture_guidelines}}``
        from the registry; a stale ``extra["culture_guidelines"] = ""`` is
        overwritten and yields byte-identical output to omitting it."""
        culture_text = "## Old Norse naming conventions\n- Use patronymics"
        composer_with_entry = PromptComposer(cast("Any", self._registry(culture_text)))
        composer_without_entry = PromptComposer(cast("Any", self._registry(culture_text)))

        ctx_with_entry = PromptContext(
            language="en",
            extra={"name_style": "old_norse", "culture_guidelines": ""},
        )
        ctx_without_entry = PromptContext(
            language="en",
            extra={"name_style": "old_norse"},
        )

        result_with = await composer_with_entry.build(LLMIntent.WRITE, ctx_with_entry)
        result_without = await composer_without_entry.build(LLMIntent.WRITE, ctx_without_entry)

        # Both substitute the resolved content (the stale extra "" is dead).
        assert culture_text in result_with.system
        assert culture_text in result_without.system
        assert "{{culture_guidelines}}" not in result_with.system
        assert "{{culture_guidelines}}" not in result_without.system
        assert result_with.system == result_without.system

    async def test_extra_entry_is_noop_when_no_name_style(self) -> None:
        """Without a ``name_style`` the Composer substitutes
        ``{{culture_guidelines}}`` with ``""``; a stale
        ``extra["culture_guidelines"] = ""`` is therefore redundant and yields
        identical output to omitting it."""
        composer_with_entry = PromptComposer(cast("Any", self._registry()))
        composer_without_entry = PromptComposer(cast("Any", self._registry()))

        ctx_with_entry = PromptContext(language="en", extra={"culture_guidelines": ""})
        ctx_without_entry = PromptContext(language="en")

        result_with = await composer_with_entry.build(LLMIntent.WRITE, ctx_with_entry)
        result_without = await composer_without_entry.build(LLMIntent.WRITE, ctx_without_entry)

        assert "{{culture_guidelines}}" not in result_with.system
        assert "{{culture_guidelines}}" not in result_without.system
        assert result_with.system == result_without.system

    async def test_no_extra_entry_substitutes_empty_without_error(self) -> None:
        """§7 post-removal guard: a context WITHOUT any ``culture_guidelines``
        key (the post-Wave-1 service state) and no ``name_style`` still
        substitutes ``{{culture_guidelines}}`` to ``""`` — never a
        ``PromptVariableError``."""
        composer = PromptComposer(cast("Any", self._registry()))
        ctx = PromptContext(language="en")

        result = await composer.build(LLMIntent.WRITE, ctx)

        assert "{{culture_guidelines}}" not in result.system
        assert result.system == "Cultural context:\n\nDone."

    async def test_no_extra_entry_substitutes_resolved_with_name_style(self) -> None:
        """§7 post-removal guard: a context WITHOUT any ``culture_guidelines``
        key but WITH a ``name_style`` resolves ``{{culture_guidelines}}`` to the
        registry content — never a ``PromptVariableError``."""
        culture_text = "## French existentialist naming\n- Sartre-style"
        composer = PromptComposer(cast("Any", self._registry(culture_text)))
        ctx = PromptContext(language="fr", extra={"name_style": "french_existential"})

        result = await composer.build(LLMIntent.WRITE, ctx)

        assert culture_text in result.system
        assert "{{culture_guidelines}}" not in result.system
