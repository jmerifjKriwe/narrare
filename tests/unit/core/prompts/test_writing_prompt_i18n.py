"""Tests for localized writing prompt resolution via the PromptRegistry cascade.

Verifies that the 6 prioritized writing modes (co_author, inline_suggest,
rewrite_selection, new_chapter, chat, interview) resolve to their localized DE/FR
bundled prompts when ``language=de`` / ``language=fr``, and that untranslated
writing modes fall back to the English bundled prompt (``bundled_en``).

Context: ADR-026 Phase 5 — feature prompts are EN-only by default; the 6 modes
here are explicit localized families. RULE-02b requires resolution exclusively
through the cascade in ``core/prompts/``.
"""

from __future__ import annotations

import pytest

from narrare_core.prompts.registry import PromptRegistry

# The six writing modes that ship localized DE/FR bundled prompts.
_LOCALIZED_MODES = (
    "co_author",
    "inline_suggest",
    "rewrite_selection",
    "new_chapter",
    "chat",
    "interview",
)

# A writing mode that is intentionally EN-only (no DE/FR bundled copy) — used to
# assert the EN-fallback branch of the cascade.
_EN_ONLY_MODE = "scene_by_scene"


class TestWritingPromptI18nCascade:
    """Localized writing prompts resolve through the standard cascade."""

    @pytest.mark.parametrize("mode", _LOCALIZED_MODES)
    async def test_de_resolves_localized_writing_prompt(self, mode: str) -> None:
        """A translated writing mode resolves to the DE bundled prompt."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="writing",
            language="de",
            mode=mode,
        )

        assert result.source == "bundled", (
            f"Expected source 'bundled' for writing/de/{mode}, got '{result.source}'"
        )
        # German role-assignment pattern (multilingual quality requirement).
        assert "Du bist" in result.system_prompt, (
            f"DE writing prompt for {mode} is not German (missing 'Du bist')"
        )

    @pytest.mark.parametrize("mode", _LOCALIZED_MODES)
    async def test_fr_resolves_localized_writing_prompt(self, mode: str) -> None:
        """A translated writing mode resolves to the FR bundled prompt."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="writing",
            language="fr",
            mode=mode,
        )

        assert result.source == "bundled", (
            f"Expected source 'bundled' for writing/fr/{mode}, got '{result.source}'"
        )
        # French role-assignment pattern (multilingual quality requirement).
        assert "Tu es" in result.system_prompt, (
            f"FR writing prompt for {mode} is not French (missing 'Tu es')"
        )

    async def test_untranslated_writing_mode_falls_back_to_en(self) -> None:
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
