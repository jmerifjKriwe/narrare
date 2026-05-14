"""Tests for ProjectAiSettingsService — project-level overrides with source metadata.

All repository calls are mocked (no I/O, no DB).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from narrare.settings.project_ai_settings_service import ProjectAiSettingsService
from narrare.settings.schemas import (
    ProjectAiSettingsResponse,
    UpdateProjectAiSettingsRequest,
)

# ---------------------------------------------------------------------------
# Fake ORM objects
# ---------------------------------------------------------------------------


@dataclass
class FakeProjectSettings:
    novel_id: uuid.UUID
    category_overrides: dict[str, Any] = field(default_factory=dict)
    intent_overrides: dict[str, Any] = field(default_factory=dict)
    token_limit_overrides: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class FakeUserAiSettings:
    user_id: uuid.UUID
    default_provider_id: uuid.UUID | None = None
    default_model: str = ""
    category_overrides: dict[str, Any] = field(default_factory=dict)
    intent_overrides: dict[str, Any] = field(default_factory=dict)
    token_limit_overrides: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def novel_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_project_ai_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_user_ai_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_project_ai_repo: AsyncMock,
    mock_user_ai_repo: AsyncMock,
) -> ProjectAiSettingsService:
    return ProjectAiSettingsService(
        project_ai_repo=mock_project_ai_repo,
        user_ai_repo=mock_user_ai_repo,
    )


# ---------------------------------------------------------------------------
# Tests — Get Settings
# ---------------------------------------------------------------------------


class TestGetProjectSettings:
    async def test_get_project_ai_settings_returns_defaults(
        self,
        service: ProjectAiSettingsService,
        mock_project_ai_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Get project AI settings for new project → returns defaults."""
        settings = FakeProjectSettings(
            novel_id=novel_id,
            category_overrides={},
            intent_overrides={},
            token_limit_overrides={},
        )
        mock_project_ai_repo.get = AsyncMock(return_value=settings)

        result = await service.get_settings(user_id, novel_id)

        assert isinstance(result, ProjectAiSettingsResponse)
        assert result.novel_id == novel_id
        assert result.category_overrides == {}
        assert result.intent_overrides == {}
        assert result.token_limit_overrides == {}

    async def test_get_project_settings_with_overrides(
        self,
        service: ProjectAiSettingsService,
        mock_project_ai_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Get project settings → returns existing overrides."""
        settings = FakeProjectSettings(
            novel_id=novel_id,
            category_overrides={"writing": {"model_id": "gpt-4o"}},
            intent_overrides={"write": {"model_id": "claude-sonnet-4-5-20251020"}},
        )
        mock_project_ai_repo.get = AsyncMock(return_value=settings)

        result = await service.get_settings(user_id, novel_id)

        assert "writing" in result.category_overrides
        assert "write" in result.intent_overrides


# ---------------------------------------------------------------------------
# Tests — Update Settings
# ---------------------------------------------------------------------------


class TestUpdateProjectSettings:
    async def test_update_project_overrides_persists_correctly(
        self,
        service: ProjectAiSettingsService,
        mock_project_ai_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Update project overrides → persists via repo."""
        updated = FakeProjectSettings(
            novel_id=novel_id,
            category_overrides={"analysis": {"model_id": "gpt-4o"}},
            intent_overrides={},
            token_limit_overrides={},
        )
        mock_project_ai_repo.update = AsyncMock(return_value=updated)

        request = UpdateProjectAiSettingsRequest(
            category_overrides={"analysis": {"model_id": "gpt-4o"}},
        )
        result = await service.update_settings(user_id, novel_id, request)

        assert isinstance(result, ProjectAiSettingsResponse)
        mock_project_ai_repo.update.assert_called_once()

    async def test_update_empty_request_does_not_call_repo_update(
        self,
        service: ProjectAiSettingsService,
        mock_project_ai_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Update with no fields → skips update, returns current settings."""
        existing = FakeProjectSettings(novel_id=novel_id)
        mock_project_ai_repo.get = AsyncMock(return_value=existing)

        request = UpdateProjectAiSettingsRequest()
        result = await service.update_settings(user_id, novel_id, request)

        mock_project_ai_repo.update.assert_not_called()
        assert isinstance(result, ProjectAiSettingsResponse)

    async def test_update_project_overrides_includes_all_fields(
        self,
        service: ProjectAiSettingsService,
        mock_project_ai_repo: AsyncMock,
        user_id: uuid.UUID,
        novel_id: uuid.UUID,
    ) -> None:
        """Update with all fields → all fields persisted."""
        updated = FakeProjectSettings(
            novel_id=novel_id,
            category_overrides={"writing": {"model_id": "m1"}},
            intent_overrides={"write": {"model_id": "m2"}},
            token_limit_overrides={"writing": {"max_tokens": 8000}},
        )
        mock_project_ai_repo.update = AsyncMock(return_value=updated)

        request = UpdateProjectAiSettingsRequest(
            category_overrides={"writing": {"model_id": "m1"}},
            intent_overrides={"write": {"model_id": "m2"}},
            token_limit_overrides={"writing": {"max_tokens": 8000}},
        )
        result = await service.update_settings(user_id, novel_id, request)

        assert "writing" in result.category_overrides
        assert "write" in result.intent_overrides
        assert "writing" in result.token_limit_overrides
