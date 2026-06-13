"""Tests for prompts/management.py — CRUD operations (list, get, save, reset)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from narrare_core.prompts._management_types import (
    PromptDetail,
    PromptInfo,
)
from narrare_core.prompts.management import PromptManagementService
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a temporary project root."""
    return tmp_path / "project"


@pytest.fixture
def tmp_bundled(tmp_path: Path) -> Path:
    """Create a temporary bundled prompts directory with a sample prompt."""
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    return bundled


def _write_bundled(
    bundled_root: Path,
    category: str,
    lang: str,
    mode: str,
    content: str,
) -> None:
    """Write a bundled prompt file."""
    p = bundled_root / category / lang / mode
    p.mkdir(parents=True, exist_ok=True)
    (p / "system.md").write_text(content)


def _write_override(
    project_root: Path,
    category: str,
    lang: str,
    mode: str,
    content: str,
) -> None:
    """Write a project-level override file."""
    p = project_root / ".narrare" / "prompts" / category / lang / mode
    p.mkdir(parents=True, exist_ok=True)
    (p / "system.md").write_text(content)


def _make_registry(bundled_root: Path, project_root: Path | None = None) -> PromptRegistry:
    """Create a registry pointing to the given temp dirs."""
    r = PromptRegistry(project_root=project_root)
    r._bundled_root = bundled_root
    return r


# ---------------------------------------------------------------------------
# list_prompts
# ---------------------------------------------------------------------------


class TestListPrompts:
    async def test_list_prompts_returns_bundled_prompts(
        self,
        tmp_bundled: Path,
    ) -> None:
        _write_bundled(
            tmp_bundled,
            "generation",
            "en",
            "names",
            (
                "---\nprompt_type: generation\nprompt_language: en"
                '\nprompt_version: "1.0.0"\n---\n\n'
                "## System Prompt\nGenerate names."
            ),
        )
        registry = _make_registry(tmp_bundled)
        svc = PromptManagementService(registry)

        result = await svc.list_prompts()
        assert len(result) >= 1
        info = result[0]
        assert isinstance(info, PromptInfo)
        assert info.prompt_id == "generation/en/names"
        assert info.category == "generation"
        assert info.language == "en"
        assert info.mode == "names"
        assert info.source == "bundled"
        assert not info.has_override

    async def test_list_prompts_filters_by_category(
        self,
        tmp_bundled: Path,
    ) -> None:
        _write_bundled(
            tmp_bundled,
            "generation",
            "en",
            "names",
            (
                "---\nprompt_type: generation\nprompt_language: en"
                '\nprompt_version: "1.0.0"\n---\n\nNames.'
            ),
        )
        _write_bundled(
            tmp_bundled,
            "writing",
            "en",
            "new_chapter",
            (
                "---\nprompt_type: writing\nprompt_language: en"
                '\nprompt_version: "1.0.0"\n---\n\nChapter.'
            ),
        )
        registry = _make_registry(tmp_bundled)
        svc = PromptManagementService(registry)

        result = await svc.list_prompts(category="generation")
        assert all(p.category == "generation" for p in result)

    async def test_list_prompts_detects_overrides(
        self,
        tmp_bundled: Path,
        tmp_project: Path,
    ) -> None:
        tmp_project.mkdir()
        _write_bundled(
            tmp_bundled,
            "generation",
            "en",
            "names",
            (
                "---\nprompt_type: generation\nprompt_language: en"
                '\nprompt_version: "1.0.0"\n---\n\nNames.'
            ),
        )
        _write_override(
            tmp_project,
            "generation",
            "en",
            "names",
            (
                "---\nprompt_type: generation\nprompt_language: en"
                '\nprompt_version: "1.0.0"\n'
                'override_of_version: "1.0.0"\n---\n\nCustom names.'
            ),
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        result = await svc.list_prompts()
        assert len(result) == 1
        assert result[0].has_override is True
        assert result[0].is_overridden is True

    async def test_list_prompts_empty_when_no_bundled(self, tmp_path: Path) -> None:
        bundled = tmp_path / "empty_bundled"
        bundled.mkdir()
        registry = _make_registry(bundled)
        svc = PromptManagementService(registry)

        result = await svc.list_prompts()
        assert result == []

    async def test_list_prompts_empty_when_bundled_root_missing(self, tmp_path: Path) -> None:
        """Bundled dir does not exist on disk → list_prompts returns []."""
        bundled = tmp_path / "nonexistent"
        registry = _make_registry(bundled)
        svc = PromptManagementService(registry)

        result = await svc.list_prompts()
        assert result == []

    async def test_list_prompts_skips_name_styles(
        self,
        tmp_bundled: Path,
    ) -> None:
        """Prompts under a name-styles sub-directory are filtered out."""
        # A real prompt so the result is not empty
        _write_bundled(
            tmp_bundled,
            "generation",
            "en",
            "names",
            '---\nprompt_version: "1.0.0"\n---\n\nNames.',
        )
        # A name-styles entry that should be skipped
        ns_dir = tmp_bundled / "generation" / "name-styles" / "en"
        ns_dir.mkdir(parents=True)
        (ns_dir / "system.md").write_text(
            '---\nprompt_version: "1.0.0"\n---\n\nName style',
        )

        registry = _make_registry(tmp_bundled)
        svc = PromptManagementService(registry)

        result = await svc.list_prompts()
        prompt_ids = [p.prompt_id for p in result]
        assert "generation/en/names" in prompt_ids
        # name-styles should not appear as a prompt
        assert not any("name-styles" in pid for pid in prompt_ids)


# ---------------------------------------------------------------------------
# get_prompt
# ---------------------------------------------------------------------------


class TestGetPrompt:
    async def test_get_prompt_returns_bundled_when_no_override(
        self,
        tmp_bundled: Path,
    ) -> None:
        _write_bundled(
            tmp_bundled,
            "generation",
            "en",
            "names",
            '---\nprompt_version: "1.0.0"\n---\n\n## System Prompt\nGenerate {{count}} names.',
        )
        registry = _make_registry(tmp_bundled)
        svc = PromptManagementService(registry)

        detail = await svc.get_prompt("generation/en/names")
        assert detail is not None
        assert isinstance(detail, PromptDetail)
        assert detail.source == "bundled"
        assert not detail.is_overridden
        assert "{{count}}" in detail.content or "count" in detail.variables

    async def test_get_prompt_returns_override_when_exists(
        self,
        tmp_bundled: Path,
        tmp_project: Path,
    ) -> None:
        tmp_project.mkdir()
        _write_bundled(
            tmp_bundled,
            "generation",
            "en",
            "names",
            '---\nprompt_version: "1.0.0"\n---\n\n## System Prompt\nBundled content.',
        )
        _write_override(
            tmp_project,
            "generation",
            "en",
            "names",
            (
                '---\nprompt_version: "1.0.0"\n'
                'override_of_version: "1.0.0"\n---\n\n'
                "## System Prompt\nCustom content."
            ),
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        detail = await svc.get_prompt("generation/en/names")
        assert detail is not None
        assert detail.source == "project"
        assert detail.is_overridden
        assert "Custom content." in detail.content
        assert "Bundled content." in detail.base_content

    async def test_get_prompt_returns_none_for_invalid_id(
        self,
        tmp_bundled: Path,
    ) -> None:
        registry = _make_registry(tmp_bundled)
        svc = PromptManagementService(registry)

        assert await svc.get_prompt("invalid") is None
        assert await svc.get_prompt("a/b") is None

    async def test_get_prompt_returns_none_for_missing_bundled(
        self,
        tmp_bundled: Path,
    ) -> None:
        registry = _make_registry(tmp_bundled)
        svc = PromptManagementService(registry)

        assert await svc.get_prompt("nonexistent/en/mode") is None


# ---------------------------------------------------------------------------
# save_override
# ---------------------------------------------------------------------------


class TestSaveOverride:
    async def test_save_override_creates_file(
        self,
        tmp_bundled: Path,
        tmp_project: Path,
    ) -> None:
        tmp_project.mkdir()
        _write_bundled(
            tmp_bundled,
            "generation",
            "en",
            "names",
            '---\nprompt_version: "1.0.0"\n---\n\nBundled.',
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        content = '---\nprompt_version: "1.0.0"\n---\n\n## System Prompt\nMy custom prompt.'
        await svc.save_override("generation/en/names", content)

        override_path = (
            tmp_project / ".narrare" / "prompts" / "generation" / "en" / "names" / "system.md"
        )
        assert override_path.exists()

    async def test_save_override_injects_version(
        self,
        tmp_bundled: Path,
        tmp_project: Path,
    ) -> None:
        tmp_project.mkdir()
        _write_bundled(
            tmp_bundled,
            "generation",
            "en",
            "names",
            '---\nprompt_version: "2.0.0"\n---\n\nBundled.',
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        content = '---\nprompt_version: "2.0.0"\n---\n\n## System Prompt\nCustom.'
        await svc.save_override("generation/en/names", content)

        override_path = (
            tmp_project / ".narrare" / "prompts" / "generation" / "en" / "names" / "system.md"
        )
        written = override_path.read_text()
        parsed = parse_frontmatter(written)
        assert parsed.metadata.get("override_of_version") == "2.0.0"

    async def test_save_override_rejects_invalid_id(
        self,
        tmp_bundled: Path,
        tmp_project: Path,
    ) -> None:
        tmp_project.mkdir()
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        with pytest.raises(ValueError, match="Invalid prompt_id"):
            await svc.save_override("bad-id", "content")
