"""Tests for prompts/_override_helpers.py — override detection and diff utilities."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from narrare_core.prompts._override_helpers import (
    detect_override_updates,
    get_bundled_version,
    inject_override_version,
)

# ---------------------------------------------------------------------------
# detect_override_updates — edge cases (early continue branches)
# ---------------------------------------------------------------------------


class TestDetectOverrideUpdates:
    async def test_skips_non_system_file(self, tmp_path: Path) -> None:
        """A file not named 'system.md' is skipped at line 42."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        bundled_root = tmp_path / "bundled"
        bundled_root.mkdir()

        p = project_root / ".narrare" / "prompts" / "writing" / "en" / "new_chapter"
        p.mkdir(parents=True)
        (p / "user.md").write_text("not system")

        result = await detect_override_updates(project_root, bundled_root)
        assert result == []

    async def test_skips_shallow_path(self, tmp_path: Path) -> None:
        """A file with fewer than 4 path parts is skipped at line 44."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        bundled_root = tmp_path / "bundled"
        bundled_root.mkdir()

        p = project_root / ".narrare" / "prompts"
        p.mkdir(parents=True)
        (p / "system.md").write_text("shallow")

        result = await detect_override_updates(project_root, bundled_root)
        assert result == []

    async def test_skips_name_styles_directory(self, tmp_path: Path) -> None:
        """A file under 'name-styles' is skipped at line 49."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        bundled_root = tmp_path / "bundled"
        bundled_root.mkdir()

        p = project_root / ".narrare" / "prompts" / "generation" / "name-styles" / "en"
        p.mkdir(parents=True)
        (p / "system.md").write_text("name style override")

        result = await detect_override_updates(project_root, bundled_root)
        assert result == []

    async def test_skips_unreadable_override_file(self, tmp_path: Path) -> None:
        """When read_text_or_none returns None for an override, skip that file (line 56)."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        bundled_root = tmp_path / "bundled"
        bundled_root.mkdir()

        p = project_root / ".narrare" / "prompts" / "writing" / "en" / "new_chapter"
        p.mkdir(parents=True)
        (p / "system.md").write_text(
            '---\noverride_of_version: "1.0.0"\n---\n\nOverride.',
        )

        target = "narrare_core.prompts._override_helpers.read_text_or_none"
        with patch(target, return_value=None):
            result = await detect_override_updates(project_root, bundled_root)

        assert result == []


# ---------------------------------------------------------------------------
# get_bundled_version
# ---------------------------------------------------------------------------


class TestGetBundledVersion:
    async def test_returns_default_when_bundled_file_missing(self) -> None:
        """get_bundled_version returns '0.0.0' for non-existent bundled path."""
        result = await get_bundled_version(Path("/nonexistent"), "writing", "en", "new_chapter")
        assert result == "0.0.0"


# ---------------------------------------------------------------------------
# inject_override_version
# ---------------------------------------------------------------------------


class TestInjectOverrideVersion:
    def test_wraps_content_without_frontmatter(self) -> None:
        """Content with no frontmatter gets wrapped in new frontmatter."""
        result = inject_override_version("Just prompt body", "1.5.0")
        assert 'override_of_version: "1.5.0"' in result
        assert "Just prompt body" in result
        assert result.startswith("---")

    def test_adds_override_field_when_absent_from_frontmatter(self) -> None:
        """Existing frontmatter without override_of_version gets the field injected."""
        content = "---\nother_field: value\n---\n\nPrompt body"
        result = inject_override_version(content, "2.0.0")
        assert 'override_of_version: "2.0.0"' in result
        assert "other_field: value" in result
        assert "Prompt body" in result

    def test_preserves_existing_override_field(self) -> None:
        """When override_of_version already present, do not replace it."""
        content = "---\nother_field: value\noverride_of_version: '3.0.0'\n---\n\nPrompt body"
        result = inject_override_version(content, "4.0.0")
        # The original override_of_version should stay
        assert "override_of_version: '3.0.0'" in result
        # The new one should not be injected (since it already exists)
        assert result.count("override_of_version") == 1

    def test_returns_content_unchanged_when_frontmatter_has_no_closing_newline(
        self,
    ) -> None:
        """Edge case: parse_frontmatter detects frontmatter but inline regex needs
        \\n after closing ---.  Content like '---\\nkey: val\\n---' hits line 132."""
        content = "---\nkey: val\n---"
        result = inject_override_version(content, "1.0.0")
        # The function returns the content unchanged (no newline after ---)
        assert result == content
