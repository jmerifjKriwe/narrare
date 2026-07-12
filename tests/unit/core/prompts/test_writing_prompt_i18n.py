"""Tests for writing prompt locale resolution via the PromptRegistry cascade.

Verifies that writing modes resolve to the English bundled prompt
(``bundled_en``) when ``language=de`` / ``language=fr``, since feature
prompts are EN-only by default (ADR-026 Phase 5). The output language is
controlled dynamically via ``{{writing_language}}`` — no localized feature
templates are needed.

Context: ADR-026 Phase 5 — feature prompts are EN-only. The 6 modes below
previously had localized DE/FR bundled copies; those were removed and all
non-EN locales now fall back to ``bundled_en``. RULE-02b requires resolution
exclusively through the cascade in ``core/prompts/``.
"""

from __future__ import annotations

import pytest

from narrare_core.prompts.registry import PromptRegistry

# The six writing modes that previously shipped localized DE/FR bundled
# prompts. After ADR-026 Phase 5, they are EN-only and fall back to
# bundled_en for non-EN locales.
_FORMERLY_LOCALIZED_MODES = (
    "co_author",
    "inline_suggest",
    "rewrite_selection",
    "new_chapter",
    "chat",
    "interview",
)

# A writing mode that has always been EN-only — used to assert the same
# bundled_en fallback behaviour as the formerly-localized modes above.
_EN_ONLY_MODE = "scene_by_scene"


class TestWritingPromptI18nCascade:
    """Writing prompts resolve to bundled_en for non-EN locales."""

    @pytest.mark.parametrize("mode", _FORMERLY_LOCALIZED_MODES)
    async def test_de_writing_prompt_falls_back_to_en(self, mode: str) -> None:
        """A writing mode at language=de falls back to bundled_en.

        After ADR-026 Phase 5, all writing feature prompts are EN-only.
        The output language is controlled via ``{{writing_language}}``.
        """
        registry = PromptRegistry()
        result = await registry.resolve(
            category="writing",
            language="de",
            mode=mode,
        )

        assert result.source == "bundled_en", (
            f"Expected source 'bundled_en' for writing/de/{mode}, got '{result.source}'"
        )
        assert result.system_prompt, f"Empty system prompt for writing/de/{mode}"

    @pytest.mark.parametrize("mode", _FORMERLY_LOCALIZED_MODES)
    async def test_fr_writing_prompt_falls_back_to_en(self, mode: str) -> None:
        """A writing mode at language=fr falls back to bundled_en."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="writing",
            language="fr",
            mode=mode,
        )

        assert result.source == "bundled_en", (
            f"Expected source 'bundled_en' for writing/fr/{mode}, got '{result.source}'"
        )
        assert result.system_prompt, f"Empty system prompt for writing/fr/{mode}"

    async def test_always_en_only_mode_also_falls_back_to_en(self) -> None:
        """An EN-only writing mode at language=de falls back to bundled_en."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="writing",
            language="de",
            mode=_EN_ONLY_MODE,
        )

        assert result.source == "bundled_en", (
            f"Expected source 'bundled_en' for writing/de/{_EN_ONLY_MODE}, got '{result.source}'"
        )
        assert result.system_prompt, "Empty system prompt for EN fallback"

    @pytest.mark.parametrize("mode", _FORMERLY_LOCALIZED_MODES)
    async def test_en_writing_prompt_resolves_directly(self, mode: str) -> None:
        """An EN writing mode resolves to bundled (not bundled_en fallback)."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="writing",
            language="en",
            mode=mode,
        )

        assert result.source == "bundled", (
            f"Expected source 'bundled' for writing/en/{mode}, got '{result.source}'"
        )
        assert result.system_prompt, f"Empty system prompt for writing/en/{mode}"
