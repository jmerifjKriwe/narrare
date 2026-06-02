"""Tests for review prompt 'respect preferences' directive (CR-04).

CR-04 coherence fix: The review prompt contains explicit guidance to treat
user preferences as intentional authorial choices, not issues to flag.

Phase 5 update: DE/FR feature-specific templates removed — DE/FR requests
cascade to EN. Tests verify EN content and EN-fallback for DE/FR.

Test strategy:
- Pure unit tests — loads bundled prompt files (no I/O beyond package data).
- Verify {{user_preferences}} variable is present.
- Verify explicit respect-preferences instruction exists in EN.
- Verify DE/FR cascade to EN (bundled_en source).
"""

from __future__ import annotations

import pytest

from narrare_core.prompts.registry import PromptRegistry


class TestReviewRespectPreferences:
    """Verify review prompts instruct the reviewer to respect user preferences."""

    async def test_en_has_user_preferences_variable(self) -> None:
        """Review prompt must contain {{user_preferences}} template variable."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="analysis",
            language="en",
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

    async def test_en_has_respect_preferences_section(self) -> None:
        """Review prompt has a dedicated User Preferences section heading."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="analysis",
            language="en",
            mode="review",
        )
        lowered = result.system_prompt.lower()
        assert "user preferences" in lowered

    @pytest.mark.parametrize("language", ["de", "fr"])
    async def test_de_fr_cascades_to_en(self, language: str) -> None:
        """DE/FR review requests cascade to EN bundled prompt."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="analysis",
            language=language,
            mode="review",
        )
        assert result.source == "bundled_en"
        assert "{{user_preferences}}" in result.system_prompt
