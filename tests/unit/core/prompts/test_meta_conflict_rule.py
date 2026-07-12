"""Tests for meta-prompt conflict resolution rule (CR-04).

After ADR-026 Phase 1, the conflict resolution rule has been moved from
the meta-prompt to NarrareUniversalRules Capability. The meta-prompt
no longer contains conflict resolution, fiction guidelines, or content
security — those are now architecturally guaranteed via Capability injection.

These tests verify:
1. The meta-prompt no longer contains the moved sections
2. NarrareUniversalRules provides the conflict resolution rule instead
"""

from __future__ import annotations

import pytest

from narrare_core.agents.capabilities import NarrareUniversalRules
from narrare_core.agents.capabilities.meta import _load_meta_prompt
from narrare_core.agents.capabilities.universal_rules import _load_universal_rules


class TestConflictResolutionMovedToCapability:
    """Verify conflict resolution has been moved from meta to NarrareUniversalRules."""

    @pytest.mark.parametrize("language", ["en", "de", "fr"])
    def test_meta_no_longer_contains_conflict_rule(self, language: str) -> None:
        """Meta prompt no longer contains conflict resolution section."""
        result = _load_meta_prompt(language)
        assert result, f"Meta prompt for {language} should not be empty"

        # These sections have been moved to NarrareUniversalRules
        if language == "en":
            assert "Conflict Resolution" not in result
            assert "outline contradicts" not in result.lower()
        elif language == "de":
            assert "Konfliktlösung" not in result
            assert "gliederung" not in result.lower() or "Gliederung" not in result
        elif language == "fr":
            assert "Résolution des conflits" not in result

    def test_capability_provides_conflict_rule_en(self) -> None:
        """NarrareUniversalRules provides the outline-over-KB rule in English."""
        rules = _load_universal_rules("en")
        assert "outline" in rules.lower()
        assert "Knowledge Base" in rules or "knowledge base" in rules.lower()

    def test_capability_provides_conflict_rule_de(self) -> None:
        """NarrareUniversalRules provides the outline-over-KB rule in German."""
        rules = _load_universal_rules("de")
        assert "Gliederung" in rules
        assert "Wissensdatenbank" in rules

    def test_capability_provides_conflict_rule_fr(self) -> None:
        """NarrareUniversalRules provides the outline-over-KB rule in French."""
        rules = _load_universal_rules("fr")
        assert "plan" in rules.lower()
        assert "base de connaissances" in rules.lower()

    def test_en_conflict_rule_in_capability_not_meta(self) -> None:
        """English conflict rule is in Capability, not in meta-prompt."""
        meta = _load_meta_prompt("en")
        cap = NarrareUniversalRules()
        # Meta should NOT have it
        assert "Conflict Resolution" not in meta
        # Capability SHOULD have it
        instructions = cap.get_instructions()
        assert instructions is not None
        assert "outline" in instructions.lower()

    def test_de_conflict_rule_in_capability_not_meta(self) -> None:
        """German conflict rule is in Capability, not in meta-prompt."""
        meta = _load_meta_prompt("de")
        cap_de = NarrareUniversalRules(_language="de")
        # Meta should NOT have it
        assert "Konfliktlösung" not in meta
        # Capability SHOULD have it
        instructions = cap_de.get_instructions()
        assert instructions is not None
        assert "Gliederung" in instructions

    def test_fr_conflict_rule_in_capability_not_meta(self) -> None:
        """French conflict rule is in Capability, not in meta-prompt."""
        meta = _load_meta_prompt("fr")
        cap_fr = NarrareUniversalRules(_language="fr")
        # Meta should NOT have it
        assert "Résolution des conflits" not in meta
        # Capability SHOULD have it
        instructions = cap_fr.get_instructions()
        assert instructions is not None
        assert "plan" in instructions.lower()
