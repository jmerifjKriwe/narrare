"""Tests for prompt variable-map constants.

Covers:
1. REQUIRED_VARS_BY_CATEGORY — expanded writing vars, planning culture_guidelines
2. MODE_REQUIRED_VARS — mode-specific hard requirements
3. SHOULD_VARS_BY_CATEGORY — recommended (non-blocking) variables

ADR-025 Phase 1 is the authoritative source for these definitions.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import setup: prompt_checks.py uses ``from prompt_vars import ...`` so the
# scripts/ directory must be on sys.path for the relative import to resolve.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[3] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import prompt_vars  # noqa: E402

# =====================================================================
# 1. REQUIRED_VARS_BY_CATEGORY
# =====================================================================


class TestRequiredVarsByCategory:
    """REQUIRED_VARS_BY_CATEGORY has the correct variable sets per category."""

    def test_writing_includes_kb_relationships(self) -> None:
        assert "kb_relationships" in prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"]

    def test_writing_includes_kb_characters(self) -> None:
        assert "kb_characters" in prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"]

    def test_writing_includes_kb_locations(self) -> None:
        assert "kb_locations" in prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"]

    def test_writing_includes_kb_factions(self) -> None:
        assert "kb_factions" in prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"]

    def test_writing_includes_culture_guidelines(self) -> None:
        assert "culture_guidelines" in prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"]

    def test_writing_has_user_preferences_and_avoidance(self) -> None:
        writing = prompt_vars.REQUIRED_VARS_BY_CATEGORY["writing"]
        assert "user_preferences" in writing
        assert "avoidance_patterns" in writing

    def test_kb_only_has_base_vars(self) -> None:
        kb = prompt_vars.REQUIRED_VARS_BY_CATEGORY["kb"]
        assert kb == {"user_preferences", "avoidance_patterns"}

    def test_analysis_only_has_base_vars(self) -> None:
        analysis = prompt_vars.REQUIRED_VARS_BY_CATEGORY["analysis"]
        assert analysis == {"user_preferences", "avoidance_patterns"}

    def test_generation_only_has_base_vars(self) -> None:
        gen = prompt_vars.REQUIRED_VARS_BY_CATEGORY["generation"]
        assert gen == {"user_preferences", "avoidance_patterns"}

    def test_chat_only_has_base_vars(self) -> None:
        chat = prompt_vars.REQUIRED_VARS_BY_CATEGORY["chat"]
        assert chat == {"user_preferences", "avoidance_patterns"}

    def test_planning_includes_culture_guidelines(self) -> None:
        planning = prompt_vars.REQUIRED_VARS_BY_CATEGORY["planning"]
        assert "culture_guidelines" in planning

    def test_planning_has_exactly_three_vars(self) -> None:
        """planning = {user_preferences, avoidance_patterns, culture_guidelines}."""
        planning = prompt_vars.REQUIRED_VARS_BY_CATEGORY["planning"]
        assert planning == {"user_preferences", "avoidance_patterns", "culture_guidelines"}


# =====================================================================
# 2. MODE_REQUIRED_VARS
# =====================================================================


class TestModeRequiredVars:
    """MODE_REQUIRED_VARS defines mode-specific hard requirements."""

    def test_extend_chapter_requires_existing_content(self) -> None:
        mode_vars = prompt_vars.MODE_REQUIRED_VARS["writing"]["extend_chapter"]
        assert "existing_content" in mode_vars

    def test_extend_requires_existing_content(self) -> None:
        mode_vars = prompt_vars.MODE_REQUIRED_VARS["writing"]["extend"]
        assert "existing_content" in mode_vars

    def test_rewrite_selection_requires_three_vars(self) -> None:
        mode_vars = prompt_vars.MODE_REQUIRED_VARS["writing"]["rewrite_selection"]
        assert mode_vars == {"selection_text", "context_before", "context_after"}

    def test_unknown_mode_has_no_extra_requirements(self) -> None:
        """Modes not in the dict have no extra requirements."""
        writing_modes = prompt_vars.MODE_REQUIRED_VARS.get("writing", {})
        assert "brainstorm" not in writing_modes
        assert "interview" not in writing_modes

    def test_non_writing_category_has_no_mode_requirements(self) -> None:
        assert "analysis" not in prompt_vars.MODE_REQUIRED_VARS
        assert "generation" not in prompt_vars.MODE_REQUIRED_VARS
        assert "chat" not in prompt_vars.MODE_REQUIRED_VARS


# =====================================================================
# 3. SHOULD_VARS_BY_CATEGORY
# =====================================================================


class TestShouldVarsByCategory:
    """SHOULD_VARS_BY_CATEGORY defines recommended (non-blocking) variables."""

    def test_writing_should_have_character_voice_profiles(self) -> None:
        assert "character_voice_profiles" in prompt_vars.SHOULD_VARS_BY_CATEGORY["writing"]

    def test_writing_should_have_kb_suggested(self) -> None:
        assert "kb_suggested" in prompt_vars.SHOULD_VARS_BY_CATEGORY["writing"]

    def test_analysis_should_have_kb_characters(self) -> None:
        assert "kb_characters" in prompt_vars.SHOULD_VARS_BY_CATEGORY["analysis"]

    def test_analysis_should_have_kb_locations(self) -> None:
        assert "kb_locations" in prompt_vars.SHOULD_VARS_BY_CATEGORY["analysis"]

    def test_analysis_should_have_kb_factions(self) -> None:
        assert "kb_factions" in prompt_vars.SHOULD_VARS_BY_CATEGORY["analysis"]

    def test_analysis_should_have_kb_relationships(self) -> None:
        assert "kb_relationships" in prompt_vars.SHOULD_VARS_BY_CATEGORY["analysis"]

    def test_kb_should_have_world_context(self) -> None:
        assert "world_context" in prompt_vars.SHOULD_VARS_BY_CATEGORY["kb"]

    def test_planning_has_no_should_vars(self) -> None:
        assert "planning" not in prompt_vars.SHOULD_VARS_BY_CATEGORY

    def test_generation_has_no_should_vars(self) -> None:
        assert "generation" not in prompt_vars.SHOULD_VARS_BY_CATEGORY

    def test_chat_has_no_should_vars(self) -> None:
        assert "chat" not in prompt_vars.SHOULD_VARS_BY_CATEGORY
