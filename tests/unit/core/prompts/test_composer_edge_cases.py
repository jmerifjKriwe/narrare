"""Edge-case tests for PromptComposer — covering lines 136 and 170.

- Line 136: freetext fallback for culture_guidelines when resolve_name_style
  returns empty/None
- Line 170: author_instructions used when neither user_prompt nor first_message available
"""

from __future__ import annotations

from typing import Any, cast

from narrare_core.llm import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import ResolvedPrompt
from tests.unit.core._bundled import bundled_prompts_root

_BUNDLED_ROOT = bundled_prompts_root()


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


class _FakeRegistryWithFallback:
    """Fake PromptRegistry where resolve_name_style returns empty string —
    triggers the freetext fallback at composer.py line 136."""

    def __init__(self) -> None:
        self._resolved = _make_resolved(system="Write about {{culture_guidelines}}.")

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
        return ""


class TestComposerCultureGuidelinesFreetextFallback:
    """Covers composer.py line 136 — freetext fallback when name_style resolution
    returns empty content."""

    async def test_culture_guidelines_fallback_when_resolve_empty(self) -> None:
        """When resolve_name_style returns empty string, the freetext fallback
        should be used, generating a prompt based on the raw name_style value."""
        fake_registry = _FakeRegistryWithFallback()
        composer = PromptComposer(cast("Any", fake_registry))

        ctx = PromptContext(
            language="en",
            project_title="Test Novel",
            extra={"name_style": "Western Fantasy"},
        )
        result = await composer.build(LLMIntent.WRITE, ctx)

        assert isinstance(result, ComposedPrompt)
        assert "Western Fantasy" in result.system
        assert "fitting the following style" in result.system
        assert "{{culture_guidelines}}" not in result.system


class _FakeRegistryNoFirstMessage:
    """Fake PromptRegistry that returns no first_message."""

    def __init__(self) -> None:
        self._resolved = _make_resolved(system="System.", first=None)

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


class TestComposerAuthorInstructionsFallback:
    """Covers composer.py line 170 — fallback to author_instructions."""

    async def test_author_instructions_used_when_no_user_prompt_or_first_message(self) -> None:
        """When user_prompt is empty and resolved.first_message is None,
        context.author_instructions should be used as the user prompt."""
        fake_registry = _FakeRegistryNoFirstMessage()
        composer = PromptComposer(cast("Any", fake_registry))

        ctx = PromptContext(
            language="en",
            project_title="Test Novel",
            author_instructions="Write a chapter about exploring the forest.",
        )
        result = await composer.build(LLMIntent.WRITE, ctx)

        assert result.user == "Write a chapter about exploring the forest."

    async def test_empty_author_instructions_fallback_to_empty_string(self) -> None:
        """When user_prompt is empty, first_message is None,
        and author_instructions is also empty/None, user should be empty string."""
        fake_registry = _FakeRegistryNoFirstMessage()
        composer = PromptComposer(cast("Any", fake_registry))

        ctx = PromptContext(
            language="en",
            project_title="Test Novel",
        )
        result = await composer.build(LLMIntent.WRITE, ctx)

        assert result.user == ""
