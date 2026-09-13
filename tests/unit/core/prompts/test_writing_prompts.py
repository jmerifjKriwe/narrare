"""Tests for bundled writing prompt files and tone variants.

Verifies that all prompt files exist with valid YAML frontmatter,
contain required variable placeholders, and have correct metadata.
Also verifies all bundled tone variant files exist with valid frontmatter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter
from tests.unit.core._bundled import bundled_prompts_root

if TYPE_CHECKING:
    from pathlib import Path

# Root of bundled prompts
_BUNDLED_ROOT = bundled_prompts_root()

# Canonical bundled feature prompt language under ADR-026 Phase 5.
# DE/FR feature copies may exist only as explicit localized families/overrides.
_WRITING_LANGUAGES = ("en",)
_WRITING_MODES = ("new_chapter", "scene_by_scene", "interview", "interactive_session")

# Dynamically discover tone IDs from the filesystem
_TONE_DIR = _BUNDLED_ROOT / "writing" / "tones"
_TONE_IDS = tuple(sorted(f.stem for f in _TONE_DIR.glob("*.md")))

# Required variable placeholders that ALL writing prompts must contain
_REQUIRED_VARIABLES = (
    "{{culture_guidelines}}",
    "{{project_title}}",
    "{{genre}}",
    "{{writing_language}}",
    "{{kb_characters}}",
    "{{kb_locations}}",
    "{{chapter_outline}}",
    "{{tone_instructions}}",
    "{{user_preferences}}",
    "{{avoidance_patterns}}",
    "{{recent_chapters}}",
)

# Mode-specific required variables (not shared by all modes)
_MODE_VARIABLES = {
    # Slice-2 word_target migration: new_chapter renders its target via
    # {{word_target_line}} (label-in-value, append-to-previous-line) — the
    # static "Word target:" label line is gone from the template.
    "new_chapter": ("{{word_target_line}}",),
    # Slice-1 word_target migration: scene_by_scene renders its target via
    # {{word_target_line}} (label-in-value, append-to-previous-line) — the
    # static "Word target per scene:" label line is gone from the template.
    "scene_by_scene": ("{{word_target_line}}",),
    "interview": (),  # interview is a Q&A flow, not draft generation
    # Slice-3 word_target migration: interactive_session renders its target
    # via {{word_target_line}} (label-in-value, append-to-previous-line) —
    # the static "Word target:" label line is gone from the template.
    "interactive_session": ("{{word_target_line}}",),
}

# Common variables that all modes share
_COMMON_VARIABLES = (
    "{{culture_guidelines}}",
    "{{project_title}}",
    "{{genre}}",
    "{{writing_language}}",
    "{{kb_characters}}",
    "{{kb_locations}}",
    "{{recent_chapters}}",
    "{{chapter_outline}}",
    "{{tone_instructions}}",
    "{{user_preferences}}",
    "{{avoidance_patterns}}",
)


def _prompt_path(language: str, mode: str) -> Path:
    return _BUNDLED_ROOT / "writing" / language / mode / "system.md"


def _tone_path(tone_id: str) -> Path:
    return _BUNDLED_ROOT / "writing" / "tones" / f"{tone_id}.md"


# ---------------------------------------------------------------------------
# Prompt file existence
# ---------------------------------------------------------------------------


class TestWritingPromptExistence:
    """Verify canonical EN writing prompt files exist."""

    @pytest.mark.parametrize("language", _WRITING_LANGUAGES)
    @pytest.mark.parametrize("mode", _WRITING_MODES)
    def test_prompt_file_exists(self, language: str, mode: str) -> None:
        """Each mode x language combination must have a system.md."""
        path = _prompt_path(language, mode)
        assert path.exists(), f"Missing writing prompt: {path}"

    def test_total_prompt_file_count(self) -> None:
        """Verify total expected canonical count: 4 modes x EN = 4 files."""
        import os

        writing_dir = _BUNDLED_ROOT / "writing"
        prompt_files = []
        # Use os.listdir() instead of Path.iterdir() to avoid unclosed
        # scandir iterator warnings (ResourceWarning on Python 3.14).
        for lang_name in os.listdir(writing_dir):
            if lang_name in _WRITING_LANGUAGES:
                lang_dir = writing_dir / lang_name
                if lang_dir.is_dir():
                    for mode_name in os.listdir(lang_dir):
                        if mode_name in _WRITING_MODES:
                            mode_dir = lang_dir / mode_name
                            if mode_dir.is_dir():
                                system_file = mode_dir / "system.md"
                                if system_file.exists():
                                    prompt_files.append(system_file)
        assert len(prompt_files) == 4, (
            f"Expected 4 writing prompt files, found {len(prompt_files)}: "
            f"{[str(p) for p in prompt_files]}"
        )


# ---------------------------------------------------------------------------
# Frontmatter validation
# ---------------------------------------------------------------------------


class TestWritingPromptFrontmatter:
    """Verify all writing prompts have valid YAML frontmatter with correct metadata."""

    @pytest.mark.parametrize("language", _WRITING_LANGUAGES)
    @pytest.mark.parametrize("mode", _WRITING_MODES)
    def test_has_valid_frontmatter(self, language: str, mode: str) -> None:
        """Each prompt must have parseable YAML frontmatter."""
        path = _prompt_path(language, mode)
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert parsed.has_frontmatter, f"No frontmatter in {path}"

    @pytest.mark.parametrize("language", _WRITING_LANGUAGES)
    @pytest.mark.parametrize("mode", _WRITING_MODES)
    def test_prompt_type_is_writing(self, language: str, mode: str) -> None:
        """Frontmatter prompt_type must be 'writing'."""
        path = _prompt_path(language, mode)
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert parsed.metadata.get("prompt_type") == "writing", (
            f"Expected prompt_type='writing' in {path}, got {parsed.metadata.get('prompt_type')}"
        )

    @pytest.mark.parametrize("language", _WRITING_LANGUAGES)
    @pytest.mark.parametrize("mode", _WRITING_MODES)
    def test_prompt_language_matches(self, language: str, mode: str) -> None:
        """Frontmatter prompt_language must match the directory language."""
        path = _prompt_path(language, mode)
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert parsed.metadata.get("prompt_language") == language, (
            f"Expected prompt_language='{language}' in {path}, "
            f"got {parsed.metadata.get('prompt_language')}"
        )

    @pytest.mark.parametrize("language", _WRITING_LANGUAGES)
    @pytest.mark.parametrize("mode", _WRITING_MODES)
    def test_has_prompt_version(self, language: str, mode: str) -> None:
        """Frontmatter must include prompt_version."""
        path = _prompt_path(language, mode)
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert "prompt_version" in parsed.metadata, f"Missing 'prompt_version' in {path}"


# ---------------------------------------------------------------------------
# Variable placeholder validation
# ---------------------------------------------------------------------------


class TestWritingPromptVariables:
    """Verify all writing prompts contain required variable placeholders."""

    @pytest.mark.parametrize("language", _WRITING_LANGUAGES)
    @pytest.mark.parametrize("mode", _WRITING_MODES)
    def test_contains_culture_guidelines(self, language: str, mode: str) -> None:
        """All writing prompts must include {{culture_guidelines}}."""
        path = _prompt_path(language, mode)
        content = path.read_text()
        assert "{{culture_guidelines}}" in content, f"Missing {{{{culture_guidelines}}}} in {path}"

    @pytest.mark.parametrize("language", _WRITING_LANGUAGES)
    @pytest.mark.parametrize("mode", _WRITING_MODES)
    def test_contains_common_variables(self, language: str, mode: str) -> None:
        """All writing prompts must include common variable placeholders."""
        path = _prompt_path(language, mode)
        content = path.read_text()
        for var in _COMMON_VARIABLES:
            assert var in content, f"Missing variable {var} in {path}"

    @pytest.mark.parametrize("language", _WRITING_LANGUAGES)
    @pytest.mark.parametrize("mode", _WRITING_MODES)
    def test_contains_mode_specific_variables(self, language: str, mode: str) -> None:
        """Each mode must include its mode-specific variable placeholders."""
        path = _prompt_path(language, mode)
        content = path.read_text()
        for var in _MODE_VARIABLES.get(mode, ()):
            assert var in content, f"Missing mode variable {var} in {path}"

    @pytest.mark.parametrize("language", _WRITING_LANGUAGES)
    @pytest.mark.parametrize("mode", _WRITING_MODES)
    def test_has_system_prompt_section(self, language: str, mode: str) -> None:
        """All writing prompts must have a ## System Prompt section."""
        path = _prompt_path(language, mode)
        content = path.read_text()
        assert "## System Prompt" in content, f"Missing '## System Prompt' section in {path}"

    @pytest.mark.parametrize("mode", ("new_chapter", "extend_chapter", "co_author"))
    def test_kb_suggested_is_labelled_lower_priority_generated_context(self, mode: str) -> None:
        """Generated KB suggestions must be visibly lower-priority and unaccepted."""
        content = _prompt_path("en", mode).read_text().lower()

        assert "{{kb_suggested}}" in content
        assert "lower-priority" in content
        assert "unaccepted" in content

    def test_inline_suggest_labels_preferences_avoidance_and_suggestions(self) -> None:
        """Inline suggest keeps dynamic context concise but explicitly labelled."""
        content = _prompt_path("en", "inline_suggest").read_text().lower()

        assert "### learned author preferences" in content
        assert "{{user_preferences}}" in content
        assert "### learned avoidance constraints" in content
        assert "{{avoidance_patterns}}" in content
        assert "### optional lower-priority generated kb suggestions" in content
        assert "{{kb_suggested}}" in content
        assert "unaccepted" in content

    def test_new_chapter_includes_cross_session_context(self) -> None:
        """new_chapter surfaces cross-session mem0 memories via a labelled section."""
        content = _prompt_path("en", "new_chapter").read_text()

        assert "{{cross_session_context}}" in content
        # Rendered as empty when no memories exist (empty-safe).


# ---------------------------------------------------------------------------
# Tone variant validation
# ---------------------------------------------------------------------------


class TestToneVariants:
    """Verify all bundled tone variant files exist with valid frontmatter."""

    @pytest.mark.parametrize("tone_id", _TONE_IDS)
    def test_tone_file_exists(self, tone_id: str) -> None:
        """Each tone variant must exist."""
        path = _tone_path(tone_id)
        assert path.exists(), f"Missing tone file: {path}"

    @pytest.mark.parametrize("tone_id", _TONE_IDS)
    def test_tone_has_valid_frontmatter(self, tone_id: str) -> None:
        """Each tone file must have parseable YAML frontmatter."""
        path = _tone_path(tone_id)
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert parsed.has_frontmatter, f"No frontmatter in {path}"

    @pytest.mark.parametrize("tone_id", _TONE_IDS)
    def test_tone_id_matches_filename(self, tone_id: str) -> None:
        """Frontmatter tone_id must match the filename."""
        path = _tone_path(tone_id)
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert parsed.metadata.get("tone_id") == tone_id, (
            f"Expected tone_id='{tone_id}' in {path}, got {parsed.metadata.get('tone_id')}"
        )

    @pytest.mark.parametrize("tone_id", _TONE_IDS)
    def test_tone_has_content_body(self, tone_id: str) -> None:
        """Each tone file must have non-empty body content."""
        path = _tone_path(tone_id)
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert len(parsed.content.strip()) > 0, f"Empty content body in {path}"


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestWritingPromptRegistryIntegration:
    """Verify the PromptRegistry can resolve all writing modes."""

    @pytest.mark.parametrize("mode", _WRITING_MODES)
    async def test_registry_resolves_writing_prompt_en(self, mode: str) -> None:
        """PromptRegistry.resolve should find each writing prompt in EN."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="writing",
            language="en",
            mode=mode,
        )
        assert result.system_prompt, f"Empty system prompt for writing/en/{mode}"
        assert result.source == "bundled", (
            f"Unexpected source '{result.source}' for writing/en/{mode}"
        )

    async def test_cascade_resolves_en_new_chapter(self) -> None:
        """Specific cascade test: writing/en/new_chapter resolves correctly."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="writing",
            language="en",
            mode="new_chapter",
        )
        assert result.source == "bundled"
        assert "creative writing assistant" in result.system_prompt.lower()
        assert result.category == "writing"
        assert result.language == "en"
        assert result.mode == "new_chapter"

    async def test_cascade_falls_back_to_en_for_unknown_language(self) -> None:
        """Non-existent language falls back to English bundled."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="writing",
            language="ja",  # Japanese — no bundled prompts
            mode="new_chapter",
        )
        assert result.source == "bundled_en"
        assert result.system_prompt

    async def test_registry_resolves_interview_mode(self) -> None:
        """Interview mode resolves with its distinct persona."""
        registry = PromptRegistry()
        result = await registry.resolve(
            category="writing",
            language="en",
            mode="interview",
        )
        assert result.source == "bundled"
        assert "interview" in result.system_prompt.lower()
