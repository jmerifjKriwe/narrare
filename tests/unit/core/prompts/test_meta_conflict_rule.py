"""Tests for meta-prompt conflict resolution rule (CR-04).

CR-04 coherence fix: All 3 meta prompts (en, de, fr) now contain a
conflict resolution paragraph stating that the outline takes priority
over the KB when they contradict.

Test strategy:
- Pure unit tests — loads bundled prompt files (no I/O beyond package data).
- Verify conflict resolution paragraph exists in all languages.
- Verify outline-over-KB priority is expressed explicitly.
"""

from __future__ import annotations

import pytest

from narrare_core.prompts.meta import MetaPromptLoader


class TestMetaConflictResolution:
    """Verify meta prompts contain outline-over-KB conflict rule."""

    @pytest.mark.parametrize("language", ["en", "de", "fr"])
    async def test_meta_contains_conflict_rule(self, language: str) -> None:
        """Meta prompt must contain the conflict resolution paragraph."""
        loader = MetaPromptLoader()
        result = await loader.load(language=language, variables={})
        assert result, f"Meta prompt for {language} should not be empty"
        lowered = result.lower()

        if language == "en":
            assert "outline" in lowered
            assert "conflict" in lowered or "contradict" in lowered
            assert "knowledge base" in lowered or "kb" in lowered
        elif language == "de":
            assert "konflikt" in lowered or "widerspruch" in lowered
            assert "gliederung" in lowered
        elif language == "fr":
            assert "conflit" in lowered
            assert "plan" in lowered

    async def test_en_conflict_rule_heading(self) -> None:
        """English meta prompt has 'Conflict Resolution' heading."""
        loader = MetaPromptLoader()
        result = await loader.load(language="en", variables={})
        assert "Conflict Resolution" in result

    async def test_de_conflict_rule_heading(self) -> None:
        """German meta prompt has 'Konfliktlösung' heading."""
        loader = MetaPromptLoader()
        result = await loader.load(language="de", variables={})
        assert "Konfliktlösung" in result

    async def test_fr_conflict_rule_heading(self) -> None:
        """French meta prompt has 'Résolution des conflits' heading."""
        loader = MetaPromptLoader()
        result = await loader.load(language="fr", variables={})
        assert "Résolution des conflits" in result

    async def test_conflict_rule_outlines_priority(self) -> None:
        """English meta prompt explicitly says outline wins over KB."""
        loader = MetaPromptLoader()
        result = await loader.load(language="en", variables={})
        lowered = result.lower()
        assert "outline" in lowered
        # The prompt says "the outline wins"
        assert (
            "wins" in lowered
            or "follow" in lowered
            or "supersede" in lowered
            or "priority" in lowered
        )
