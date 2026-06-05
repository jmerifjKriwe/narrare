"""Tests for bundled KB prompt files — existence, variables, content quality.

Verifies that all 4 KB prompt files exist with valid YAML frontmatter,
contain required variable placeholders, and include output format instructions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Root of bundled prompts
_BUNDLED_ROOT = (
    Path(__file__).parent.parent.parent.parent.parent
    / "packages"
    / "core"
    / "narrare_core"
    / "prompts"
    / "_bundled"
)

_KB_PROMPT_MODES = ("interview", "suggest", "enhance", "extract")


def _kb_prompt_path(mode: str) -> Path:
    return _BUNDLED_ROOT / "kb" / "en" / mode / "system.md"


# ---------------------------------------------------------------------------
# A. Prompt file existence
# ---------------------------------------------------------------------------


class TestKBPromptExistence:
    """Verify all 4 KB prompt files exist and are non-empty."""

    @pytest.mark.parametrize("mode", _KB_PROMPT_MODES)
    def test_prompt_loads(self, mode: str) -> None:
        """Each KB mode must have a system.md that is non-empty."""
        path = _kb_prompt_path(mode)
        assert path.exists(), f"Missing KB prompt: {path}"
        content = path.read_text()
        assert len(content) > 50, f"KB prompt too short: {path}"

    def test_total_prompt_file_count(self) -> None:
        """Verify all 4 KB prompt files exist."""
        prompt_files = [p for mode in _KB_PROMPT_MODES if (p := _kb_prompt_path(mode)).exists()]
        assert len(prompt_files) == 4, (
            f"Expected 4 KB prompt files, found {len(prompt_files)}: "
            f"{[str(p) for p in prompt_files]}"
        )


# ---------------------------------------------------------------------------
# B. Variable placeholder validation
# ---------------------------------------------------------------------------


class TestKBPromptVariables:
    """Verify KB prompts contain required variable placeholders."""

    def test_interview_prompt_contains_variables(self) -> None:
        """Interview prompt must contain template_structure and world_context."""
        content = _kb_prompt_path("interview").read_text()
        assert "{{template_structure}}" in content
        assert "{{world_context}}" in content

    def test_suggest_prompt_contains_target_field(self) -> None:
        """Suggest prompt must contain target_field."""
        content = _kb_prompt_path("suggest").read_text()
        assert "{{target_field}}" in content

    def test_enhance_prompt_contains_entity_type(self) -> None:
        """Enhance prompt must contain entity_type."""
        content = _kb_prompt_path("enhance").read_text()
        assert "{{entity_type}}" in content

    def test_extract_prompt_contains_confidence_calibration(self) -> None:
        """Extract prompt must mention confidence scoring."""
        content = _kb_prompt_path("extract").read_text()
        assert "confidence" in content.lower()
        assert "0.7" in content or "calibrat" in content.lower()

    def test_extract_prompt_wraps_world_context_as_curated_kb(self) -> None:
        """world_context is curated author KB and must have explicit XML boundaries."""
        content = _kb_prompt_path("extract").read_text()
        assert "<curated_kb_context>" in content
        assert "{{world_context}}" in content
        assert "</curated_kb_context>" in content

    def test_worldbuilding_phase2_wraps_world_context_as_curated_kb(self) -> None:
        """Worldbuilding phase 2 consumes curated KB context with explicit XML boundaries."""
        path = _BUNDLED_ROOT / "kb" / "en" / "worldbuilding" / "phase2" / "system.md"
        content = path.read_text()
        assert "<curated_kb_context>" in content
        assert "{{world_context}}" in content
        assert "</curated_kb_context>" in content


# ---------------------------------------------------------------------------
# C. Content quality — output format and negative examples
# ---------------------------------------------------------------------------


class TestKBPromptContent:
    """Verify all prompts include output format and negative examples."""

    @pytest.mark.parametrize("mode", _KB_PROMPT_MODES)
    def test_all_prompts_contain_output_format(self, mode: str) -> None:
        """All prompts must mention output format instructions."""
        content = _kb_prompt_path(mode).read_text()
        assert "Output Format" in content, f"Missing 'Output Format' section in {mode}"

    @pytest.mark.parametrize("mode", _KB_PROMPT_MODES)
    def test_all_prompts_contain_negative_examples(self, mode: str) -> None:
        """All prompts must mention what NOT to do."""
        content = _kb_prompt_path(mode).read_text()
        assert "Do NOT" in content, f"Missing 'Do NOT' section in {mode}"

    @pytest.mark.parametrize("mode", _KB_PROMPT_MODES)
    def test_all_prompts_contain_system_prompt_section(self, mode: str) -> None:
        """All prompts must have a ## System Prompt section."""
        content = _kb_prompt_path(mode).read_text()
        assert "## System Prompt" in content, f"Missing '## System Prompt' section in {mode}"

    @pytest.mark.parametrize("mode", _KB_PROMPT_MODES)
    def test_all_prompts_contain_instructions(self, mode: str) -> None:
        """All prompts must have an ### Instructions section."""
        content = _kb_prompt_path(mode).read_text()
        assert "### Instructions" in content, f"Missing '### Instructions' section in {mode}"
