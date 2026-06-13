"""Tests for prompts/management.py — cascade info."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from narrare_core.prompts.management import PromptManagementService
from narrare_core.prompts.registry import PromptRegistry

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


def _make_registry(bundled_root: Path, project_root: Path | None = None) -> PromptRegistry:
    """Create a registry pointing to the given temp dirs."""
    r = PromptRegistry(project_root=project_root)
    r._bundled_root = bundled_root
    return r


# ---------------------------------------------------------------------------
# cascade_info
# ---------------------------------------------------------------------------


class TestCascadeInfo:
    async def test_cascade_info_shows_all_levels(
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
            "---\n---\n\nBundled.",
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        cascade = await svc.cascade_info("generation/en/names")
        assert len(cascade) >= 3

        levels = {c.level for c in cascade}
        assert "project" in levels
        assert "user" in levels
        assert "bundled" in levels

        # Bundled should exist, project/user should not (no overrides)
        for entry in cascade:
            if entry.level == "bundled":
                assert entry.exists

    async def test_cascade_info_shows_en_fallback_for_non_en(
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
            "---\n---\n\nBundled EN.",
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        cascade = await svc.cascade_info("generation/de/names")
        levels = {c.level for c in cascade}
        assert "bundled_en" in levels

    async def test_cascade_info_empty_for_invalid_id(
        self,
        tmp_bundled: Path,
    ) -> None:
        registry = _make_registry(tmp_bundled)
        svc = PromptManagementService(registry)

        result = await svc.cascade_info("invalid")
        assert result == []

    async def test_cascade_info_without_project_root(
        self,
        tmp_bundled: Path,
    ) -> None:
        """cascade_info with project_root=None skips project-level path (branch 207->211)."""
        _write_bundled(
            tmp_bundled,
            "generation",
            "en",
            "names",
            "---\n---\n\nBundled.",
        )
        registry = _make_registry(tmp_bundled, project_root=None)
        svc = PromptManagementService(registry)

        cascade = await svc.cascade_info("generation/en/names")

        assert len(cascade) == 2  # user + bundled (no project)
        levels = {c.level for c in cascade}
        assert "project" not in levels
        assert "user" in levels
        assert "bundled" in levels
