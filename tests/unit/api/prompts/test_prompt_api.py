"""Unit tests for PromptManagementApiService — wraps core PromptManagementService.

Tests the API layer's conversion of core dataclasses to Pydantic schemas.
All core service calls are mocked — no I/O, no filesystem access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from narrare.prompts.schemas import (
    CascadePathResponse,
    DiffResponse,
    PromptDetailResponse,
    PromptInfoResponse,
    SaveOverrideRequest,
    UpdateInfoResponse,
)
from narrare_core.prompts._management_types import (
    CascadePath,
    PromptDetail,
    PromptInfo,
    UpdateInfo,
)

# ---------------------------------------------------------------------------
# Fake core PromptManagementService
# ---------------------------------------------------------------------------


class FakeCorePromptService:
    """Fake core service implementing the methods used by PromptManagementApiService."""

    def __init__(self) -> None:
        self.prompts: list[PromptInfo] = []
        self.detail: PromptDetail | None = None
        self.saved_overrides: list[tuple[str, str]] = []
        self.deleted_overrides: list[str] = []
        self.cascade_paths: list[CascadePath] = []
        self.updates: list[UpdateInfo] = []
        self.diff_data: tuple[str, str] | None = None

    async def list_prompts(self, *, category: str | None = None) -> list[PromptInfo]:
        if category is None:
            return self.prompts
        return [p for p in self.prompts if p.category == category]

    async def get_prompt(self, prompt_id: str) -> PromptDetail | None:
        return self.detail

    async def save_override(self, prompt_id: str, content: str) -> None:
        self.saved_overrides.append((prompt_id, content))

    async def reset_override(self, prompt_id: str) -> bool:
        self.deleted_overrides.append(prompt_id)
        return prompt_id in [o[0] for o in self.saved_overrides]

    async def cascade_info(self, prompt_id: str) -> list[CascadePath]:
        return self.cascade_paths

    async def detect_updates(self) -> list[UpdateInfo]:
        return self.updates

    async def get_diff(self, prompt_id: str) -> tuple[str, str] | None:
        return self.diff_data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_core() -> FakeCorePromptService:
    return FakeCorePromptService()


@pytest.fixture
def service(fake_core: FakeCorePromptService) -> Any:
    from narrare.prompts.service import PromptManagementApiService

    return PromptManagementApiService(core_service=fake_core)  # type: ignore[arg-type]


def _make_prompt_info(**overrides: Any) -> PromptInfo:
    defaults: dict[str, Any] = {
        "prompt_id": "writing/en/new_chapter",
        "name": "writing/new_chapter (en)",
        "category": "writing",
        "language": "en",
        "mode": "new_chapter",
        "source": "bundled",
        "has_override": False,
        "prompt_version": "1.0.0",
        "is_overridden": False,
    }
    defaults.update(overrides)
    return PromptInfo(**defaults)


def _make_prompt_detail(**overrides: Any) -> PromptDetail:
    defaults: dict[str, Any] = {
        "prompt_id": "writing/en/new_chapter",
        "content": "You are a creative writing assistant.",
        "base_content": "You are a creative writing assistant.",
        "source": "bundled",
        "is_overridden": False,
        "variables": ["project_title", "language"],
        "metadata": {"prompt_version": "1.0.0"},
    }
    defaults.update(overrides)
    return PromptDetail(**defaults)


# ---------------------------------------------------------------------------
# list_prompts
# ---------------------------------------------------------------------------


class TestListPrompts:
    async def test_list_prompts_returns_all_with_source_indicators(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        fake_core.prompts = [
            _make_prompt_info(source="bundled", has_override=False),
            _make_prompt_info(
                prompt_id="writing/de/new_chapter",
                name="writing/new_chapter (de)",
                language="de",
                source="bundled",
                has_override=True,
                is_overridden=True,
            ),
        ]

        result = await service.list_prompts()

        assert len(result) == 2
        assert all(isinstance(r, PromptInfoResponse) for r in result)
        assert result[0].source == "bundled"
        assert result[0].has_override is False
        assert result[1].has_override is True

    async def test_list_prompts_filters_by_category(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        fake_core.prompts = [
            _make_prompt_info(category="writing"),
            _make_prompt_info(
                prompt_id="analysis/en/general",
                name="analysis/general (en)",
                category="analysis",
                mode="general",
            ),
        ]

        result = await service.list_prompts(category="writing")

        assert len(result) == 1
        assert result[0].category == "writing"

    async def test_list_prompts_returns_empty_when_none(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        result = await service.list_prompts()
        assert result == []


# ---------------------------------------------------------------------------
# get_prompt
# ---------------------------------------------------------------------------


class TestGetPrompt:
    async def test_get_prompt_returns_content_and_metadata(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        fake_core.detail = _make_prompt_detail()

        result = await service.get_prompt("writing/en/new_chapter")

        assert result is not None
        assert isinstance(result, PromptDetailResponse)
        assert result.prompt_id == "writing/en/new_chapter"
        assert result.content == "You are a creative writing assistant."
        assert result.source == "bundled"
        assert result.is_overridden is False
        assert "project_title" in result.variables

    async def test_get_prompt_returns_none_when_not_found(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        fake_core.detail = None

        result = await service.get_prompt("nonexistent/prompt")

        assert result is None


# ---------------------------------------------------------------------------
# save_override
# ---------------------------------------------------------------------------


class TestSaveOverride:
    async def test_save_override_creates_new(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        request = SaveOverrideRequest(content="My custom prompt content.")

        await service.save_override("writing/en/new_chapter", request)

        assert len(fake_core.saved_overrides) == 1
        assert fake_core.saved_overrides[0] == (
            "writing/en/new_chapter",
            "My custom prompt content.",
        )

    async def test_save_override_updates_existing(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        request1 = SaveOverrideRequest(content="First override")
        request2 = SaveOverrideRequest(content="Updated override")

        await service.save_override("writing/en/new_chapter", request1)
        await service.save_override("writing/en/new_chapter", request2)

        assert len(fake_core.saved_overrides) == 2
        assert fake_core.saved_overrides[1][1] == "Updated override"


# ---------------------------------------------------------------------------
# reset_override
# ---------------------------------------------------------------------------


class TestResetOverride:
    async def test_reset_override_deletes_and_falls_back(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        fake_core.saved_overrides.append(("writing/en/new_chapter", "custom"))

        result = await service.reset_override("writing/en/new_chapter")

        assert result is True
        assert "writing/en/new_chapter" in fake_core.deleted_overrides

    async def test_reset_override_returns_false_when_none_exists(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        result = await service.reset_override("writing/en/new_chapter")

        assert result is False


# ---------------------------------------------------------------------------
# detect_updates
# ---------------------------------------------------------------------------


class TestDetectUpdates:
    async def test_detect_updates_finds_newer_bundled_version(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        fake_core.updates = [
            UpdateInfo(
                prompt_id="writing/en/new_chapter",
                override_version="1.0.0",
                current_bundled_version="1.1.0",
            ),
        ]

        result = await service.detect_updates()

        assert len(result) == 1
        assert isinstance(result[0], UpdateInfoResponse)
        assert result[0].prompt_id == "writing/en/new_chapter"
        assert result[0].override_version == "1.0.0"
        assert result[0].current_bundled_version == "1.1.0"

    async def test_detect_updates_returns_empty_when_none(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        result = await service.detect_updates()
        assert result == []


# ---------------------------------------------------------------------------
# get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    async def test_diff_shows_changes_between_override_and_bundled(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        fake_core.diff_data = ("My custom content", "Original bundled content")

        result = await service.get_diff("writing/en/new_chapter")

        assert result is not None
        assert isinstance(result, DiffResponse)
        assert result.override_content == "My custom content"
        assert result.bundled_content == "Original bundled content"
        assert result.prompt_id == "writing/en/new_chapter"

    async def test_diff_returns_none_when_no_override(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        fake_core.diff_data = None

        result = await service.get_diff("writing/en/new_chapter")

        assert result is None


# ---------------------------------------------------------------------------
# cascade_info
# ---------------------------------------------------------------------------


class TestCascadeInfo:
    async def test_cascade_resolution_shows_all_levels(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        fake_core.cascade_paths = [
            CascadePath(
                level="project",
                path=Path("/project/.narrare/prompts/writing/en/new_chapter/system.md"),
                exists=False,
            ),
            CascadePath(
                level="user",
                path=Path("/home/user/.narrare/prompts/writing/en/new_chapter/system.md"),
                exists=False,
            ),
            CascadePath(
                level="bundled", path=Path("/bundled/writing/en/new_chapter/system.md"), exists=True
            ),
        ]

        result = await service.cascade_info("writing/en/new_chapter")

        assert len(result) == 3
        assert all(isinstance(r, CascadePathResponse) for r in result)
        assert result[0].level == "project"
        assert result[0].exists is False
        assert result[2].level == "bundled"
        assert result[2].exists is True

    async def test_cascade_empty_for_invalid_id(
        self, service: Any, fake_core: FakeCorePromptService
    ) -> None:
        fake_core.cascade_paths = []

        result = await service.cascade_info("invalid")

        assert result == []
