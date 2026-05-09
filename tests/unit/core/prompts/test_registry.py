"""Tests for prompts/registry.py"""

from __future__ import annotations

from pathlib import Path

import pytest

from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.errors import PromptNotFoundError


@pytest.fixture
def tmp_prompt_dir(tmp_path: Path) -> Path:
    """Create a temporary bundled prompts directory."""
    return tmp_path


@pytest.fixture
def registry(tmp_path: Path) -> PromptRegistry:
    """Registry pointing at a temp directory (no real bundled prompts)."""
    r = PromptRegistry()
    r._bundled_root = tmp_path / "bundled"
    r._bundled_root.mkdir()
    return r


def _write_prompt(root: Path, category: str, lang: str, mode: str, content: str) -> None:
    p = root / category / lang / mode
    p.mkdir(parents=True, exist_ok=True)
    (p / "system.md").write_text(content)


class TestPromptRegistryResolve:
    async def test_resolves_bundled_prompt(self, registry: PromptRegistry) -> None:
        _write_prompt(
            registry._bundled_root,
            "writing",
            "en",
            "new_chapter",
            "## System Prompt\n\nWrite a chapter.\n\n## First Message\n\nHello!",
        )
        result = await registry.resolve(category="writing", language="en", mode="new_chapter")
        assert result.system_prompt == "Write a chapter."
        assert result.first_message == "Hello!"
        assert result.source == "bundled"

    async def test_falls_back_to_english(self, registry: PromptRegistry) -> None:
        _write_prompt(
            registry._bundled_root,
            "writing",
            "en",
            "new_chapter",
            "## System Prompt\n\nEnglish fallback.",
        )
        result = await registry.resolve(category="writing", language="de", mode="new_chapter")
        assert result.system_prompt == "English fallback."
        assert result.source == "bundled_en"

    async def test_raises_when_not_found(self, registry: PromptRegistry) -> None:
        with pytest.raises(PromptNotFoundError):
            await registry.resolve(category="writing", language="en", mode="nonexistent_mode")

    async def test_db_content_highest_priority(self, registry: PromptRegistry) -> None:
        _write_prompt(
            registry._bundled_root,
            "writing",
            "en",
            "new_chapter",
            "## System Prompt\n\nBundled prompt.",
        )
        result = await registry.resolve(
            category="writing",
            language="en",
            mode="new_chapter",
            db_content="## System Prompt\n\nDB override.",
        )
        assert result.system_prompt == "DB override."
        assert result.source == "db"

    async def test_project_override_beats_bundled(
        self, registry: PromptRegistry, tmp_path: Path
    ) -> None:
        project_root = tmp_path / "project"
        registry._project_root = project_root

        # Write bundled
        _write_prompt(
            registry._bundled_root,
            "writing",
            "en",
            "new_chapter",
            "## System Prompt\n\nBundled.",
        )
        # Write project override
        override = project_root / ".narrare" / "prompts" / "writing" / "en" / "new_chapter"
        override.mkdir(parents=True)
        (override / "system.md").write_text("## System Prompt\n\nProject override.")

        result = await registry.resolve(category="writing", language="en", mode="new_chapter")
        assert result.system_prompt == "Project override."
        assert result.source == "project"

    async def test_genre_specific_prompt_preferred(self, registry: PromptRegistry) -> None:
        _write_prompt(
            registry._bundled_root,
            "writing",
            "en",
            "new_chapter",
            "## System Prompt\n\nGeneric.",
        )
        # Write genre-specific
        p = registry._bundled_root / "writing" / "en" / "new_chapter"
        (p / "system_fantasy.md").write_text("## System Prompt\n\nFantasy specific.")

        result = await registry.resolve(
            category="writing", language="en", mode="new_chapter", genre="fantasy"
        )
        assert result.system_prompt == "Fantasy specific."
        assert result.source == "bundled_genre"
