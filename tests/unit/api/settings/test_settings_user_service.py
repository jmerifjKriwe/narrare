"""Unit tests for user settings — repository contract via in-memory Fake."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from narrare.settings.contracts import UserSettingsRepositoryProtocol
from narrare.settings.models import UserSettings
from narrare.settings.schemas import UpdateUserSettingsRequest
from tests.fakes.fake_repositories import CallRecord

# ======================================================================
# In-memory Fake for UserSettingsRepository
# ======================================================================


class FakeUserSettingsRepository:
    """In-memory fake for UserSettingsRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, UserSettings] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *settings: UserSettings) -> None:
        for s in settings:
            self._store[s.user_id] = s

    async def get(self, user_id: uuid.UUID) -> UserSettings:
        self.calls.append(CallRecord("get", kwargs={"user_id": user_id}))
        settings = self._store.get(user_id)
        if not settings:
            # Mirror real repo: auto-create with defaults
            settings = UserSettings()
            settings.user_id = user_id
            settings.display_name = ""
            settings.ui_language = "en"
            settings.theme = "system"
            settings.updated_at = datetime.now(UTC)
            self._store[user_id] = settings
        return settings

    async def update(self, user_id: uuid.UUID, request: UpdateUserSettingsRequest) -> UserSettings:
        self.calls.append(CallRecord("update", kwargs={"user_id": user_id}))
        settings = await self.get(user_id)
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(settings, field, value)
        return settings


# ======================================================================
# Protocol conformance checks
# ======================================================================


class TestProtocolConformance:
    def test_fake_user_settings_repo_satisfies_protocol(self) -> None:
        fake = FakeUserSettingsRepository()
        assert isinstance(fake, UserSettingsRepositoryProtocol)


# ======================================================================
# User Settings tests
# ======================================================================


@pytest.fixture
def user_settings_repo() -> FakeUserSettingsRepository:
    return FakeUserSettingsRepository()


class TestUserSettingsGet:
    async def test_get_with_existing_settings_returns_settings(
        self, user_settings_repo: FakeUserSettingsRepository
    ) -> None:
        user_id = uuid.uuid4()
        settings = UserSettings()
        settings.user_id = user_id
        settings.display_name = "Alice"
        settings.ui_language = "de"
        settings.theme = "dark"
        settings.updated_at = datetime.now(UTC)
        user_settings_repo.seed(settings)

        result = await user_settings_repo.get(user_id)

        assert result.user_id == user_id
        assert result.display_name == "Alice"
        assert result.ui_language == "de"
        assert result.theme == "dark"

    async def test_get_without_existing_settings_creates_defaults(
        self, user_settings_repo: FakeUserSettingsRepository
    ) -> None:
        user_id = uuid.uuid4()

        result = await user_settings_repo.get(user_id)

        assert result.user_id == user_id
        assert result.display_name == ""
        assert result.ui_language == "en"
        assert result.theme == "system"

    async def test_get_records_call(self, user_settings_repo: FakeUserSettingsRepository) -> None:
        user_id = uuid.uuid4()
        await user_settings_repo.get(user_id)
        assert len(user_settings_repo.calls) == 1
        assert user_settings_repo.calls[0].method == "get"


class TestUserSettingsUpdate:
    async def test_update_creates_settings_when_missing(
        self, user_settings_repo: FakeUserSettingsRepository
    ) -> None:
        user_id = uuid.uuid4()
        request = UpdateUserSettingsRequest(display_name="Bob", theme="dark")

        result = await user_settings_repo.update(user_id, request)

        assert result.display_name == "Bob"
        assert result.theme == "dark"
        # ui_language not provided → remains default
        assert result.ui_language == "en"

    async def test_update_modifies_existing_settings(
        self, user_settings_repo: FakeUserSettingsRepository
    ) -> None:
        user_id = uuid.uuid4()
        settings = UserSettings()
        settings.user_id = user_id
        settings.display_name = "Alice"
        settings.ui_language = "en"
        settings.theme = "light"
        settings.updated_at = datetime.now(UTC)
        user_settings_repo.seed(settings)

        request = UpdateUserSettingsRequest(ui_language="de", theme="dark")
        result = await user_settings_repo.update(user_id, request)

        assert result.display_name == "Alice"  # unchanged
        assert result.ui_language == "de"
        assert result.theme == "dark"

    async def test_update_with_none_fields_does_not_change_them(
        self, user_settings_repo: FakeUserSettingsRepository
    ) -> None:
        user_id = uuid.uuid4()
        settings = UserSettings()
        settings.user_id = user_id
        settings.display_name = "Original"
        settings.ui_language = "fr"
        settings.theme = "system"
        settings.updated_at = datetime.now(UTC)
        user_settings_repo.seed(settings)

        # Only update display_name, leave others as None
        request = UpdateUserSettingsRequest(display_name="Updated")
        result = await user_settings_repo.update(user_id, request)

        assert result.display_name == "Updated"
        assert result.ui_language == "fr"  # unchanged
        assert result.theme == "system"  # unchanged

    async def test_update_records_call(
        self, user_settings_repo: FakeUserSettingsRepository
    ) -> None:
        user_id = uuid.uuid4()
        await user_settings_repo.update(user_id, UpdateUserSettingsRequest(display_name="X"))
        assert any(c.method == "update" for c in user_settings_repo.calls)
