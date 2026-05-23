"""Tests for review prompt 'respect preferences' directive (CR-04).

CR-04 coherence fix: All 3 review prompts (en, de, fr) now contain
explicit guidance to treat user preferences as intentional authorial
choices, not issues to flag.

Test strategy:
- Pure unit tests — loads bundled prompt files (no I/O beyond package data).
- Verify {{user_preferences}} variable is present in all languages.
- Verify explicit respect-preferences instruction exists.
"""

from __future__ import annotations

import pytest

from narrare_core.prompts.registry import PromptRegistry


class TestReviewRespectPreferences:
    """Verify review prompts instruct the reviewer to respect user preferences."""

    @pytest.mark.parametrize("language", ["en", "de", "fr"])
    async def test_review_has_user_preferences_variable(self, language: str) -> None:
        """Review prompt must contain {{user_preferences}} template variable."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="analysis",
            language=language,
            mode="review",
        )
        assert "{{user_preferences}}" in result.system_prompt

    async def test_en_has_intentional_instruction(self) -> None:
        """English review prompt says preferences are 'intentional'."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="analysis",
            language="en",
            mode="review",
        )
        lowered = result.system_prompt.lower()
        assert "intentional" in lowered
        # Must say NOT to flag as issue
        assert "not" in lowered and "issue" in lowered

    async def test_de_has_bewusst_instruction(self) -> None:
        """German review prompt says preferences are 'bewusst' (deliberate)."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="analysis",
            language="de",
            mode="review",
        )
        lowered = result.system_prompt.lower()
        assert "absichtlich" in lowered or "bewusst" in lowered

    async def test_fr_has_intentionnel_instruction(self) -> None:
        """French review prompt says preferences are 'intentionnels' (intentional)."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="analysis",
            language="fr",
            mode="review",
        )
        lowered = result.system_prompt.lower()
        assert "intentionnel" in lowered or "choix" in lowered

    @pytest.mark.parametrize("language", ["en", "de", "fr"])
    async def test_review_has_respect_preferences_section(self, language: str) -> None:
        """Review prompt has a dedicated User Preferences section heading."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="analysis",
            language=language,
            mode="review",
        )
        lowered = result.system_prompt.lower()
        if language == "en":
            assert "user preferences" in lowered
        elif language == "de":
            assert "nutzereinstellungen" in lowered
        elif language == "fr":
            assert "préférences utilisateur" in lowered
