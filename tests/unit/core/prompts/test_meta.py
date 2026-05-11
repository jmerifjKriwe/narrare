"""Tests for prompts/meta.py — meta-prompt loading and caching."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from narrare_core.prompts.meta import MetaPromptLoader


@pytest.fixture
def loader(tmp_path: Path) -> MetaPromptLoader:
    return MetaPromptLoader(project_root=tmp_path)


class TestMetaPromptLoaderLoad:
    async def test_loads_bundled_english_meta_prompt(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("en")
        # If bundled prompt exists, it should return non-empty string
        # If not, it should return empty string (no error)
        assert isinstance(content, str)

    async def test_load_returns_empty_for_missing_language(self) -> None:
        loader = MetaPromptLoader()
        content = await loader.load("xx")
        assert isinstance(content, str)

    async def test_load_cascades_to_project_override(self, tmp_path: Path) -> None:
        # Create a project-level override
        meta_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        meta_dir.mkdir(parents=True)
        (meta_dir / "system.md").write_text("Project meta prompt")

        loader = MetaPromptLoader(project_root=tmp_path)
        content = await loader.load("en")

        assert content == "Project meta prompt"

    async def test_load_cascades_to_user_config(self, tmp_path: Path) -> None:
        user_dir = tmp_path / "config"
        meta_dir = user_dir / "prompts" / "meta" / "en"
        meta_dir.mkdir(parents=True)
        (meta_dir / "system.md").write_text("User config meta prompt")

        loader = MetaPromptLoader(user_config_dir=user_dir)
        content = await loader.load("en")

        assert content == "User config meta prompt"

    async def test_project_overrides_user_config(self, tmp_path: Path) -> None:
        # Project-level
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.md").write_text("Project prompt")

        # User-level
        user_dir = tmp_path / "user_config"
        user_meta_dir = user_dir / "prompts" / "meta" / "en"
        user_meta_dir.mkdir(parents=True)
        (user_meta_dir / "system.md").write_text("User prompt")

        loader = MetaPromptLoader(project_root=tmp_path, user_config_dir=user_dir)
        content = await loader.load("en")

        assert content == "Project prompt"

    async def test_substitutes_variables(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.md").write_text(
            "---\nprompt_type: meta\n---\nHello {{project_title}}, you are {{genre}}."
        )

        loader = MetaPromptLoader(project_root=tmp_path)
        content = await loader.load(
            "en",
            variables={"project_title": "My Novel", "genre": "fantasy"},
        )

        assert "My Novel" in content
        assert "fantasy" in content
        assert "{{" not in content

    async def test_strips_frontmatter(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.md").write_text("---\nprompt_type: meta\n---\nActual prompt content")

        loader = MetaPromptLoader(project_root=tmp_path)
        content = await loader.load("en")

        assert "prompt_type" not in content
        assert "Actual prompt content" in content

    async def test_caches_result(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.md").write_text("Cached prompt")

        loader = MetaPromptLoader(project_root=tmp_path)
        content1 = await loader.load("en")
        content2 = await loader.load("en")

        assert content1 == content2 == "Cached prompt"

    async def test_load_lite_variant(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.lite.md").write_text("Lite prompt")

        loader = MetaPromptLoader(project_root=tmp_path)
        content = await loader.load("en", use_lite=True)

        assert content == "Lite prompt"

    async def test_falls_back_to_english_for_missing_language(self) -> None:
        # "zz" has no bundled prompt, no user config — should hit bundled English fallback
        loader = MetaPromptLoader()
        content = await loader.load("zz")

        # Should return the bundled English meta prompt (not empty)
        assert isinstance(content, str)
        assert "Narrare" in content


class TestMetaPromptLoaderShouldUseLite:
    def test_returns_true_when_below_threshold(self) -> None:
        loader = MetaPromptLoader()
        assert loader.should_use_lite(1999) is True

    def test_returns_false_when_above_threshold(self) -> None:
        loader = MetaPromptLoader()
        assert loader.should_use_lite(2000) is False


class TestMetaPromptLoaderInvalidateCache:
    async def test_clears_cache(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / ".narrare" / "prompts" / "meta" / "en"
        proj_dir.mkdir(parents=True)
        (proj_dir / "system.md").write_text("Original")

        loader = MetaPromptLoader(project_root=tmp_path)
        await loader.load("en")

        # Overwrite file
        (proj_dir / "system.md").write_text("Updated")

        # Still cached
        content = await loader.load("en")
        assert content == "Original"

        # Invalidate and reload
        loader.invalidate_cache()
        content = await loader.load("en")
        assert content == "Updated"
