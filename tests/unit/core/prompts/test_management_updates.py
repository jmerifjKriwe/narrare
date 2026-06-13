"""Tests for prompts/management.py — update detection and diff comparison."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from narrare_core.prompts._management_types import UpdateInfo
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
# detect_updates
# ---------------------------------------------------------------------------


class TestDetectUpdates:
    async def test_detects_version_mismatch(
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
            '---\nprompt_version: "2.0.0"\n---\n\nNew bundled.',
        )
        _write_override(
            tmp_project,
            "generation",
            "en",
            "names",
            '---\noverride_of_version: "1.0.0"\n---\n\nOld override.',
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        updates = await svc.detect_updates()
        assert len(updates) == 1
        assert isinstance(updates[0], UpdateInfo)
        assert updates[0].prompt_id == "generation/en/names"
        assert updates[0].override_version == "1.0.0"
        assert updates[0].current_bundled_version == "2.0.0"

    async def test_no_update_when_versions_match(
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
        _write_override(
            tmp_project,
            "generation",
            "en",
            "names",
            '---\noverride_of_version: "1.0.0"\n---\n\nOverride.',
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        updates = await svc.detect_updates()
        assert len(updates) == 0

    async def test_override_without_version_field_detected(
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
        _write_override(
            tmp_project,
            "generation",
            "en",
            "names",
            "---\n---\n\nOverride without version field.",
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        updates = await svc.detect_updates()
        assert len(updates) == 1
        assert updates[0].override_version == "unknown"

    async def test_detect_updates_empty_without_project_root(
        self,
        tmp_bundled: Path,
    ) -> None:
        registry = _make_registry(tmp_bundled)
        svc = PromptManagementService(registry)

        updates = await svc.detect_updates()
        assert updates == []

    async def test_detect_updates_empty_when_no_prompts_dir(
        self,
        tmp_bundled: Path,
        tmp_project: Path,
    ) -> None:
        tmp_project.mkdir()
        # No .narrare/prompts/ directory created
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        updates = await svc.detect_updates()
        assert updates == []


# ---------------------------------------------------------------------------
# get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    async def test_get_diff_returns_both_contents(
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
            "---\n---\n\nBundled content for diff.",
        )
        _write_override(
            tmp_project,
            "generation",
            "en",
            "names",
            "---\n---\n\nOverride content for diff.",
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        diff = await svc.get_diff("generation/en/names")
        assert diff is not None
        override_content, bundled_content = diff
        assert "Override content" in override_content
        assert "Bundled content" in bundled_content

    async def test_get_diff_returns_none_when_no_override(
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

        diff = await svc.get_diff("generation/en/names")
        assert diff is None

    async def test_get_diff_returns_none_for_invalid_id(
        self,
        tmp_bundled: Path,
    ) -> None:
        registry = _make_registry(tmp_bundled)
        svc = PromptManagementService(registry)

        diff = await svc.get_diff("invalid")
        assert diff is None


# ---------------------------------------------------------------------------
# list_prompts — unreadable file handling
# ---------------------------------------------------------------------------


class TestListPromptsUnreadable:
    """Coverage for edge cases in list_prompts that require mocking."""

    async def test_skips_unreadable_prompt(self, tmp_path: Path) -> None:
        """When read_text_or_none returns None, skip that prompt (line 96)."""
        from unittest.mock import patch

        bundled = tmp_path / "bundled"
        bundled.mkdir()
        p = bundled / "generation" / "en" / "names"
        p.mkdir(parents=True)
        (p / "system.md").write_text("---\nprompt_version: '1.0.0'\n---\n\nNames.")

        registry = PromptRegistry()
        registry._bundled_root = bundled
        svc = PromptManagementService(registry)

        target = "narrare_core.prompts.management.read_text_or_none"
        with patch(target, return_value=None):
            result = await svc.list_prompts()

        assert result == []


# ---------------------------------------------------------------------------
# reset_override
# ---------------------------------------------------------------------------


class TestResetOverride:
    async def test_reset_override_deletes_file(
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
        _write_override(
            tmp_project,
            "generation",
            "en",
            "names",
            "---\n---\n\nOverride content.",
        )
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        result = await svc.reset_override("generation/en/names")
        assert result is True

        # File should be gone
        override_path = (
            tmp_project / ".narrare" / "prompts" / "generation" / "en" / "names" / "system.md"
        )
        assert not override_path.exists()

    async def test_reset_override_returns_false_when_none(
        self,
        tmp_bundled: Path,
        tmp_project: Path,
    ) -> None:
        tmp_project.mkdir()
        registry = _make_registry(tmp_bundled, project_root=tmp_project)
        svc = PromptManagementService(registry)

        result = await svc.reset_override("generation/en/names")
        assert result is False

    async def test_reset_override_returns_false_for_invalid_id(
        self,
        tmp_bundled: Path,
    ) -> None:
        """Invalid prompt_id (not 3 parts) → return False."""
        registry = _make_registry(tmp_bundled)
        svc = PromptManagementService(registry)

        result = await svc.reset_override("invalid")
        assert result is False

        result = await svc.reset_override("a/b")
        assert result is False
