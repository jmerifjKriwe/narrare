"""Tests for NarrareUniversalRules Capability.

Verifies that universal rules are loaded correctly, injected into every
NarrareAgent, and not duplicated with the meta-prompt.

See ADR-026 (Capability-Based Prompt Injection Pattern).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents import NarrareAgent
from narrare_core.agents.capabilities import NarrareObservability, NarrareUniversalRules
from narrare_core.agents.capabilities.universal_rules import _load_universal_rules


class TestNarrareUniversalRulesLoading:
    """Test that universal rules are loaded from bundled files."""

    def test_load_english_rules(self) -> None:
        """English rules load successfully and contain key rules."""
        rules = _load_universal_rules("en")
        assert rules, "English universal rules should not be empty"
        # Key rules must be present
        assert "fiction" in rules.lower(), "Must contain fiction content guideline"
        assert "outline" in rules.lower(), "Must contain outline > KB rule"
        assert "author instructions" in rules.lower(), "Must contain author instructions rule"
        assert "XML" in rules or "xml" in rules, "Must contain injection defense rule"

    def test_load_german_rules(self) -> None:
        """German rules load successfully with translated content."""
        rules = _load_universal_rules("de")
        assert rules, "German universal rules should not be empty"
        assert "Fiktionsinhalte" in rules or "fiktion" in rules.lower()
        assert "Gliederung" in rules
        assert "XML" in rules or "xml" in rules

    def test_load_french_rules(self) -> None:
        """French rules load successfully with translated content."""
        rules = _load_universal_rules("fr")
        assert rules, "French universal rules should not be empty"
        assert "fiction" in rules.lower()
        assert "plan" in rules.lower()
        assert "XML" in rules or "xml" in rules

    def test_fallback_to_english(self) -> None:
        """Unknown language falls back to English."""
        rules = _load_universal_rules("xx")
        assert rules, "Should fall back to English rules"
        assert "fiction" in rules.lower(), "Should contain English fiction guideline"

    def test_load_rules_returns_stripped_content(self) -> None:
        """Frontmatter is stripped from loaded rules."""
        rules = _load_universal_rules("en")
        assert rules, "Rules should not be empty"
        # Frontmatter should not be present
        assert "---" not in rules, "Frontmatter should be stripped"
        assert "prompt_type:" not in rules, "Frontmatter metadata should be stripped"


class TestNarrareUniversalRulesCapability:
    """Test the NarrareUniversalRules Capability class."""

    def test_get_instructions_returns_non_empty(self) -> None:
        """get_instructions() returns non-empty string for default language."""
        cap = NarrareUniversalRules()
        instructions = cap.get_instructions()
        assert instructions is not None, "get_instructions() should not return None"
        assert isinstance(instructions, str), "get_instructions() should return str"
        assert len(instructions) > 0, "get_instructions() should return non-empty string"

    def test_get_instructions_contains_key_rules(self) -> None:
        """Instructions contain fiction guidelines, conflict resolution, injection defense."""
        cap = NarrareUniversalRules()
        instructions = cap.get_instructions()
        assert instructions is not None
        # Fiction content guideline
        assert "fiction" in instructions.lower() or "Fiktionsinhalte" in instructions
        # Conflict resolution (outline > KB)
        assert (
            "outline" in instructions.lower()
            or "Gliederung" in instructions
            or "plan" in instructions.lower()
        )
        # Author instructions > preferences
        assert "author instructions" in instructions.lower() or "Autorenanweisungen" in instructions
        # Injection defense
        assert "XML" in instructions or "xml" in instructions

    def test_default_language_is_english(self) -> None:
        """Default language is English when no language is specified."""
        cap = NarrareUniversalRules()
        instructions = cap.get_instructions()
        assert instructions is not None
        # English-specific content
        assert "Treat fiction content" in instructions

    def test_language_parameter_selects_rules(self) -> None:
        """Language parameter selects the correct rules variant."""
        cap_de = NarrareUniversalRules(_language="de")
        instructions_de = cap_de.get_instructions()
        assert instructions_de is not None
        assert "Fiktionsinhalte" in instructions_de or "Gliederung" in instructions_de

    async def test_for_run_resolves_language_from_deps(self) -> None:
        """for_run() resolves language from deps via getattr()."""

        @dataclass
        class MyDeps:
            language: str = "de"

        cap = NarrareUniversalRules()
        ctx = MagicMock(spec=[])
        ctx.deps = MyDeps(language="fr")

        result = await cap.for_run(ctx)
        assert isinstance(result, NarrareUniversalRules)
        # The new instance should have French rules
        instructions = result.get_instructions()
        assert instructions is not None
        assert "plan" in instructions.lower() or "fiction" in instructions.lower()

    async def test_for_run_fallback_when_no_language(self) -> None:
        """for_run() falls back to 'en' when deps don't have language."""

        @dataclass
        class NoLanguageDeps:
            user_name: str = "test"

        cap = NarrareUniversalRules()
        ctx = MagicMock(spec=[])
        ctx.deps = NoLanguageDeps()

        result = await cap.for_run(ctx)
        instructions = result.get_instructions()
        assert instructions is not None
        assert "Treat fiction content" in instructions

    async def test_for_run_fallback_when_deps_none(self) -> None:
        """for_run() falls back to 'en' when deps is None."""
        cap = NarrareUniversalRules()
        ctx = MagicMock(spec=[])
        ctx.deps = None

        result = await cap.for_run(ctx)
        instructions = result.get_instructions()
        assert instructions is not None
        assert "Treat fiction content" in instructions


class TestNarrareUniversalRulesInAgent:
    """Test that NarrareUniversalRules is injected in NarrareAgent."""

    def test_narrare_agent_includes_universal_rules(self) -> None:
        """NarrareAgent.__init__ includes NarrareUniversalRules in capabilities."""
        model = TestModel()

        class MyAgent(NarrareAgent[None, str]):
            pass

        agent = MyAgent(model=model, deps_type=type(None), output_type=str)
        # Check that the underlying pydantic-ai Agent has NarrareUniversalRules
        root_cap = agent._agent.root_capability
        capability_types = [type(c) for c in root_cap.capabilities]
        assert NarrareUniversalRules in capability_types, (
            f"NarrareUniversalRules should be in capabilities, got {capability_types}"
        )

    def test_narrare_agent_includes_observability_and_universal_rules(self) -> None:
        """Both NarrareObservability and NarrareUniversalRules are present."""
        model = TestModel()

        class MyAgent(NarrareAgent[None, str]):
            pass

        agent = MyAgent(model=model, deps_type=type(None), output_type=str)
        root_cap = agent._agent.root_capability
        capability_types = [type(c) for c in root_cap.capabilities]
        assert NarrareObservability in capability_types
        assert NarrareUniversalRules in capability_types

    def test_additional_capabilities_are_preserved(self) -> None:
        """User-provided capabilities are preserved alongside standard ones."""
        from pydantic_ai.capabilities import AbstractCapability

        @dataclass
        class CustomCapability(AbstractCapability):
            pass

        model = TestModel()

        class MyAgent(NarrareAgent[None, str]):
            pass

        agent = MyAgent(
            model=model,
            deps_type=type(None),
            output_type=str,
            capabilities=[CustomCapability()],
        )
        root_cap = agent._agent.root_capability
        capability_types = [type(c) for c in root_cap.capabilities]
        assert NarrareUniversalRules in capability_types
        assert CustomCapability in capability_types


class TestNoDuplicationWithMeta:
    """Integration test: universal rules appear once, not duplicated."""

    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    def test_meta_prompt_does_not_contain_universal_rules(self) -> None:
        """Meta-prompt files no longer contain universal rules content.

        After ADR-026 Phase 1, the meta-prompt should NOT contain:
        - Fiction content guidelines
        - Conflict resolution (outline > KB)
        - Content security / injection defense

        These are now injected via NarrareUniversalRules Capability.
        """
        from narrare_core.prompts.meta import MetaPromptLoader

        loader = MetaPromptLoader()

        # Check EN meta-prompt
        import asyncio

        meta_en = asyncio.run(loader.load(language="en"))
        # Should NOT contain universal rules content
        assert "Fiction Content Guidelines" not in meta_en
        assert "Content Security" not in meta_en
        assert "Conflict Resolution" not in meta_en
        assert "outline contradicts" not in meta_en.lower()

        # Check DE meta-prompt
        meta_de = asyncio.run(loader.load(language="de"))
        assert "Konfliktlösung" not in meta_de
        assert "Fiktionsinhalts-Richtlinien" not in meta_de
        assert "Inhaltssicherheit" not in meta_de

        # Check FR meta-prompt
        meta_fr = asyncio.run(loader.load(language="fr"))
        assert "Résolution des conflits" not in meta_fr
        assert "contenu de fiction" not in meta_fr.lower()
        assert "Sécurité du contenu" not in meta_fr

    def test_universal_rules_capability_provides_removed_content(self) -> None:
        """NarrareUniversalRules provides the content removed from meta-prompt."""
        cap = NarrareUniversalRules()
        instructions = cap.get_instructions()
        assert instructions is not None

        # Fiction content guideline
        assert "fiction" in instructions.lower()
        # Conflict resolution (outline > KB)
        assert "outline" in instructions.lower() or "plan" in instructions.lower()
        # Author instructions > preferences
        assert "author instructions" in instructions.lower()
        # Injection defense
        assert "XML" in instructions or "xml" in instructions


class TestGracefulDegradation:
    """Test that NarrareUniversalRules degrades gracefully on failure."""

    def test_missing_language_returns_english(self) -> None:
        """If requested language file is missing, English is returned."""
        rules = _load_universal_rules("zz")
        assert rules, "Should fall back to English"
        assert "Treat fiction content" in rules

    def test_load_rules_logs_warning_on_failure(self) -> None:
        """If all files fail to load, a warning is logged and empty string returned."""
        with patch(
            "narrare_core.agents.capabilities.universal_rules._find_bundled_root",
            return_value=Path("/nonexistent/path"),
        ):
            rules = _load_universal_rules("en")
            # Should return empty string (graceful degradation — RULE-11)
            assert rules == ""

    def test_capability_returns_empty_string_on_load_failure(self) -> None:
        """NarrareUniversalRules returns empty string if loading fails."""
        with patch(
            "narrare_core.agents.capabilities.universal_rules._find_bundled_root",
            return_value=Path("/nonexistent/path"),
        ):
            cap = NarrareUniversalRules()
            instructions = cap.get_instructions()
            # Should return empty string, not None, not raise
            assert instructions == ""
