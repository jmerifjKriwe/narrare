"""Tests for bundled writing prompt files and tone variants.

Verifies that all prompt files exist with valid YAML frontmatter,
contain required variable placeholders, and have correct metadata.
Also verifies all bundled tone variant files exist with valid frontmatter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter

# Root of bundled prompts
_BUNDLED_ROOT = Path(__file__).parent.parent.parent.parent.parent / (
    "packages/core/narrare_core/prompts/_bundled"
)

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
    "{{language}}",
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
    "new_chapter": ("{{word_target}}",),
    "scene_by_scene": ("{{word_target}}",),
    "interview": (),  # interview is a Q&A flow, not draft generation
    "interactive_session": ("{{word_target}}",),
}

# Common variables that all modes share
_COMMON_VARIABLES = (
    "{{culture_guidelines}}",
    "{{project_title}}",
    "{{genre}}",
    "{{language}}",
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
        writing_dir = _BUNDLED_ROOT / "writing"
        prompt_files = []
        for lang_dir in writing_dir.iterdir():
            if lang_dir.is_dir() and lang_dir.name in _WRITING_LANGUAGES:
                for mode_dir in lang_dir.iterdir():
                    if mode_dir.is_dir() and mode_dir.name in _WRITING_MODES:
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
