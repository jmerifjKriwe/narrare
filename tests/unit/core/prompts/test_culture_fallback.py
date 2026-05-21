"""Tests for culture definition resolution fallback in PromptRegistry.

Verifies that:
- Culture resolved in requested language when file exists
- Fallback to English when requested language has no culture file
- Culture not found in any language returns empty string with warning logged
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.prompts.registry import PromptRegistry

if TYPE_CHECKING:
    from pathlib import Path


def _write_culture(
    root: Path,
    category: str,
    lang: str,
    culture_id: str,
    content: str,
) -> None:
    """Write a culture definition file at the expected path."""
    p = root / category / "name-styles" / lang
    p.mkdir(parents=True, exist_ok=True)
    (p / f"{culture_id}.md").write_text(content)


def _make_registry(tmp_path: Path) -> PromptRegistry:
    """Create a PromptRegistry with temp directories and no project root."""
    registry = PromptRegistry()
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    registry._bundled_root = bundled
    registry._user_config_dir = tmp_path / "user_config"
    (tmp_path / "user_config" / "prompts").mkdir(parents=True, exist_ok=True)
    return registry


class TestCultureFallback:
    """Task 7.7: Culture fallback tests for PromptRegistry.resolve_culture()."""

    async def test_culture_resolved_in_requested_language(self, tmp_path: Path) -> None:
        """Culture resolved in requested language (e.g., 'de') when file exists."""
        registry = _make_registry(tmp_path)
        _write_culture(
            registry._bundled_root,
            "writing",
            "de",
            "german_literary",
            (
                "---\nculture_id: german_literary\n---\n\n"
                "## German Literary Traditions\n- Follow Schiller."
            ),
        )

        result = await registry.resolve_culture(
            category="writing",
            language="de",
            culture_id="german_literary",
        )

        assert "German Literary Traditions" in result
        assert "Follow Schiller." in result
        assert "---" not in result  # frontmatter stripped

    async def test_fallback_to_english_when_language_missing(self, tmp_path: Path) -> None:
        """Fallback to English when requested language has no culture file."""
        registry = _make_registry(tmp_path)
        # Only write the English version
        _write_culture(
            registry._bundled_root,
            "writing",
            "en",
            "german_literary",
            "## English Version of German Culture\n- Follow standard structure.",
        )

        result = await registry.resolve_culture(
            category="writing",
            language="de",
            culture_id="german_literary",
        )

        assert "English Version of German Culture" in result
        assert "Follow standard structure." in result

    async def test_culture_not_found_returns_empty_string(self, tmp_path: Path) -> None:
        """Culture not found in any language: returns empty string."""
        registry = _make_registry(tmp_path)

        result = await registry.resolve_culture(
            category="writing",
            language="ja",
            culture_id="nonexistent_culture",
        )

        assert result == ""

    async def test_project_override_takes_priority(self, tmp_path: Path) -> None:
        """Project-level culture file takes priority over bundled."""
        registry = _make_registry(tmp_path)
        project_root = tmp_path / "project"
        registry._project_root = project_root

        # Write bundled version
        _write_culture(
            registry._bundled_root,
            "writing",
            "en",
            "gothic",
            "Bundled gothic culture.",
        )
        # Write project override
        _write_culture(
            project_root / ".narrare" / "prompts",
            "writing",
            "en",
            "gothic",
            "Project-level gothic culture.",
        )

        result = await registry.resolve_culture(
            category="writing",
            language="en",
            culture_id="gothic",
        )

        assert result == "Project-level gothic culture."

    async def test_no_en_fallback_when_language_is_en(self, tmp_path: Path) -> None:
        """When language is 'en', no separate EN fallback path is searched."""
        registry = _make_registry(tmp_path)
        # Don't write any files

        result = await registry.resolve_culture(
            category="writing",
            language="en",
            culture_id="nonexistent",
        )

        assert result == ""

    async def test_frontmatter_stripped_from_culture(self, tmp_path: Path) -> None:
        """Frontmatter is stripped from culture content."""
        registry = _make_registry(tmp_path)
        _write_culture(
            registry._bundled_root,
            "writing",
            "en",
            "minimalist",
            "---\nculture_id: minimalist\nversion: '1.0'\n---\n\nKeep it simple. No adverbs.",
        )

        result = await registry.resolve_culture(
            category="writing",
            language="en",
            culture_id="minimalist",
        )

        assert "Keep it simple. No adverbs." in result
        assert "culture_id" not in result
        assert "version" not in result
