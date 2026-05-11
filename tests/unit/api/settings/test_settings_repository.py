"""Unit tests for settings/repository.py — UserSettings + ProjectSettings DB queries."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.settings.models import ProjectSettings, UserSettings
from narrare.settings.repository import ProjectSettingsRepository, UserSettingsRepository
from narrare.settings.schemas import UpdateProjectSettingsRequest, UpdateUserSettingsRequest


def _make_user_settings(**kwargs: object) -> UserSettings:
    from sqlalchemy.orm.attributes import set_attribute

    settings = UserSettings()
    set_attribute(settings, "user_id", kwargs.get("user_id", uuid.uuid4()))
    set_attribute(settings, "display_name", kwargs.get("display_name", ""))
    set_attribute(settings, "ui_language", kwargs.get("ui_language", "en"))
    set_attribute(settings, "theme", kwargs.get("theme", "system"))
    return settings


def _make_project_settings(**kwargs: object) -> ProjectSettings:
    from sqlalchemy.orm.attributes import set_attribute

    settings = ProjectSettings()
    set_attribute(settings, "novel_id", kwargs.get("novel_id", uuid.uuid4()))
    set_attribute(settings, "autosave_interval", kwargs.get("autosave_interval", 30))
    set_attribute(settings, "default_language", kwargs.get("default_language", "en"))
    set_attribute(settings, "ai_provider", kwargs.get("ai_provider", ""))
    set_attribute(settings, "ai_model", kwargs.get("ai_model", ""))
    set_attribute(settings, "model_overrides", kwargs.get("model_overrides", "{}"))
    return settings


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# UserSettingsRepository
# ---------------------------------------------------------------------------


class TestUserSettingsRepositoryGet:
    async def test_returns_existing_settings(self, mock_session: MagicMock) -> None:
        uid = uuid.uuid4()
        settings = _make_user_settings(user_id=uid)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = settings
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = UserSettingsRepository(mock_session)
        result = await repo.get(uid)

        assert result == settings

    async def test_creates_default_when_not_found(self, mock_session: MagicMock) -> None:
        uid = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        repo = UserSettingsRepository(mock_session)
        result = await repo.get(uid)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert result.user_id == uid


class TestUserSettingsRepositoryUpdate:
    async def test_updates_provided_fields(self, mock_session: MagicMock) -> None:
        uid = uuid.uuid4()
        settings = _make_user_settings(user_id=uid)
        mock_session.flush = AsyncMock()

        # Mock get to return existing settings
        repo = UserSettingsRepository(mock_session)
        repo.get = AsyncMock(return_value=settings)  # type: ignore[reportPrivateUsage]

        result = await repo.update(uid, UpdateUserSettingsRequest(display_name="New Name"))

        assert result.display_name == "New Name"
        mock_session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# ProjectSettingsRepository
# ---------------------------------------------------------------------------


class TestProjectSettingsRepositoryGet:
    async def test_returns_existing_settings(self, mock_session: MagicMock) -> None:
        nid = uuid.uuid4()
        settings = _make_project_settings(novel_id=nid)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = settings
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = ProjectSettingsRepository(mock_session)
        result = await repo.get(nid)

        assert result == settings

    async def test_creates_default_when_not_found(self, mock_session: MagicMock) -> None:
        nid = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        repo = ProjectSettingsRepository(mock_session)
        result = await repo.get(nid)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert result.novel_id == nid


class TestProjectSettingsRepositoryUpdate:
    async def test_updates_provided_fields(self, mock_session: MagicMock) -> None:
        nid = uuid.uuid4()
        settings = _make_project_settings(novel_id=nid)
        mock_session.flush = AsyncMock()

        repo = ProjectSettingsRepository(mock_session)
        repo.get = AsyncMock(return_value=settings)  # type: ignore[reportPrivateUsage]

        result = await repo.update(
            nid, UpdateProjectSettingsRequest(ai_provider="anthropic", ai_model="claude")
        )

        assert result.ai_provider == "anthropic"
        assert result.ai_model == "claude"
        mock_session.flush.assert_called_once()
