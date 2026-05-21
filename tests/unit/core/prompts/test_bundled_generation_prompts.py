"""Tests for bundled generation prompt files and culture definitions.

Verifies that all prompt files exist with valid YAML frontmatter,
contain required placeholders, and have correct metadata fields.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from narrare_core.shared.frontmatter import parse_frontmatter

# Root of bundled prompts
_BUNDLED_ROOT = Path(__file__).parent.parent.parent.parent.parent / (
    "packages/core/narrare_core/prompts/_bundled"
)

# Expected name generation language dirs
_NAME_LANGUAGES = ("en", "de", "fr")

# Expected culture IDs and languages
_CULTURE_IDS = ("fantasy", "modern", "scifi")
_CULTURE_LANGUAGES = ("en", "de", "fr")


class TestNameGenerationPrompts:
    """Verify bundled name generation prompt files."""

    @pytest.mark.parametrize("language", _NAME_LANGUAGES)
    def test_name_prompt_exists(self, language: str) -> None:
        """Each language must have a system.md for name generation."""
        path = _BUNDLED_ROOT / "generation" / language / "names" / "system.md"
        assert path.exists(), f"Missing name generation prompt: {path}"

    @pytest.mark.parametrize("language", _NAME_LANGUAGES)
    def test_name_prompt_has_valid_frontmatter(self, language: str) -> None:
        """Each name generation prompt must have parseable YAML frontmatter."""
        path = _BUNDLED_ROOT / "generation" / language / "names" / "system.md"
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert parsed.has_frontmatter, f"No frontmatter in {path}"
        assert parsed.metadata.get("prompt_type") == "generation"
        assert parsed.metadata.get("prompt_language") == language
        assert "prompt_version" in parsed.metadata

    @pytest.mark.parametrize("language", _NAME_LANGUAGES)
    def test_name_prompt_contains_culture_placeholder(self, language: str) -> None:
        """Name generation prompts must include {{culture_guidelines}}."""
        path = _BUNDLED_ROOT / "generation" / language / "names" / "system.md"
        content = path.read_text()
        assert "{{culture_guidelines}}" in content, (
            f"Missing {{culture_guidelines}} placeholder in {path}"
        )

    @pytest.mark.parametrize("language", _NAME_LANGUAGES)
    def test_name_prompt_contains_generation_variables(self, language: str) -> None:
        """Name generation prompts must include expected variable placeholders."""
        path = _BUNDLED_ROOT / "generation" / language / "names" / "system.md"
        content = path.read_text()
        expected_vars = ("{{count}}", "{{name_type}}", "{{gender}}", "{{existing_names}}")
        for var in expected_vars:
            assert var in content, f"Missing variable {var} in {path}"


class TestCultureDefinitions:
    """Verify bundled culture definition files."""

    @pytest.mark.parametrize("culture_id", _CULTURE_IDS)
    @pytest.mark.parametrize("language", _CULTURE_LANGUAGES)
    def test_culture_definition_exists(
        self,
        culture_id: str,
        language: str,
    ) -> None:
        """Each name_style x language combination must have a definition file."""
        path = _BUNDLED_ROOT / "generation" / "name-styles" / language / f"{culture_id}.md"
        assert path.exists(), f"Missing name_style definition: {path}"

    @pytest.mark.parametrize("culture_id", _CULTURE_IDS)
    @pytest.mark.parametrize("language", _CULTURE_LANGUAGES)
    def test_culture_has_valid_frontmatter(
        self,
        culture_id: str,
        language: str,
    ) -> None:
        """Name style definitions must have parseable frontmatter."""
        path = _BUNDLED_ROOT / "generation" / "name-styles" / language / f"{culture_id}.md"
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert parsed.has_frontmatter, f"No frontmatter in {path}"

    @pytest.mark.parametrize("culture_id", _CULTURE_IDS)
    @pytest.mark.parametrize("language", _CULTURE_LANGUAGES)
    def test_culture_has_required_fields(
        self,
        culture_id: str,
        language: str,
    ) -> None:
        """Name style definitions must have culture_id, culture_name, language, version."""
        path = _BUNDLED_ROOT / "generation" / "name-styles" / language / f"{culture_id}.md"
        content = path.read_text()
        parsed = parse_frontmatter(content)
        required_fields = ("culture_id", "culture_name", "language", "version")
        for field in required_fields:
            assert field in parsed.metadata, (
                f"Missing field '{field}' in {path}. Available: {list(parsed.metadata.keys())}"
            )

    @pytest.mark.parametrize("culture_id", _CULTURE_IDS)
    @pytest.mark.parametrize("language", _CULTURE_LANGUAGES)
    def test_culture_metadata_values(
        self,
        culture_id: str,
        language: str,
    ) -> None:
        """Name style definition metadata values must be correct."""
        path = _BUNDLED_ROOT / "generation" / "name-styles" / language / f"{culture_id}.md"
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert parsed.metadata["culture_id"] == culture_id
        assert parsed.metadata["language"] == language

    @pytest.mark.parametrize("culture_id", _CULTURE_IDS)
    @pytest.mark.parametrize("language", _CULTURE_LANGUAGES)
    def test_culture_has_content_body(
        self,
        culture_id: str,
        language: str,
    ) -> None:
        """Name style definitions must have non-empty body content."""
        path = _BUNDLED_ROOT / "generation" / "name-styles" / language / f"{culture_id}.md"
        content = path.read_text()
        parsed = parse_frontmatter(content)
        assert len(parsed.content.strip()) > 0, f"Empty content body in {path}"

    def test_total_culture_file_count(self) -> None:
        """Verify total expected count: 3 styles x 3 languages = 9 files."""
        styles_dir = _BUNDLED_ROOT / "generation" / "name-styles"
        md_files = list(styles_dir.rglob("*.md"))
        assert len(md_files) == 9, (
            f"Expected 9 name-style files, found {len(md_files)}: {[str(p) for p in md_files]}"
        )
