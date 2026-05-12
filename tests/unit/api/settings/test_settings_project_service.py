"""Unit tests for project settings — repository contract and schema validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from narrare.settings.contracts import ProjectSettingsRepositoryProtocol
from narrare.settings.models import ProjectSettings
from narrare.settings.schemas import (
    ProjectSettingsResponse,
    UpdateProjectSettingsRequest,
    UpdateUserSettingsRequest,
    UserSettingsResponse,
)
from tests.fakes.fake_repositories import CallRecord

# ======================================================================
# In-memory Fake for ProjectSettingsRepository
# ======================================================================


class FakeProjectSettingsRepository:
    """In-memory fake for ProjectSettingsRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, ProjectSettings] = {}
        self.calls: list[CallRecord] = []

    def seed(self, *settings: ProjectSettings) -> None:
        for s in settings:
            self._store[s.novel_id] = s

    async def get(self, novel_id: uuid.UUID) -> ProjectSettings:
        self.calls.append(CallRecord("get", kwargs={"novel_id": novel_id}))
        settings = self._store.get(novel_id)
        if not settings:
            # Mirror real repo: auto-create with defaults
            settings = ProjectSettings()
            settings.novel_id = novel_id
            settings.autosave_interval = 30
            settings.default_language = "en"
            settings.ai_provider = ""
            settings.ai_model = ""
            settings.model_overrides = "{}"
            settings.updated_at = datetime.now(UTC)
            self._store[novel_id] = settings
        return settings

    async def update(
        self, novel_id: uuid.UUID, request: UpdateProjectSettingsRequest
    ) -> ProjectSettings:
        self.calls.append(CallRecord("update", kwargs={"novel_id": novel_id}))
        settings = await self.get(novel_id)
        for field, value in request.model_dump(exclude_none=True).items():
            setattr(settings, field, value)
        return settings


# ======================================================================
# Protocol conformance check
# ======================================================================


class TestProtocolConformance:
    def test_fake_project_settings_repo_satisfies_protocol(self) -> None:
        fake = FakeProjectSettingsRepository()
        assert isinstance(fake, ProjectSettingsRepositoryProtocol)


# ======================================================================
# Project Settings tests
# ======================================================================


@pytest.fixture
def project_settings_repo() -> FakeProjectSettingsRepository:
    return FakeProjectSettingsRepository()


class TestProjectSettingsGet:
    async def test_get_with_existing_settings_returns_settings(
        self, project_settings_repo: FakeProjectSettingsRepository
    ) -> None:
        novel_id = uuid.uuid4()
        settings = ProjectSettings()
        settings.novel_id = novel_id
        settings.autosave_interval = 60
        settings.default_language = "de"
        settings.ai_provider = "anthropic"
        settings.ai_model = "claude-3"
        settings.model_overrides = "{}"
        settings.updated_at = datetime.now(UTC)
        project_settings_repo.seed(settings)

        result = await project_settings_repo.get(novel_id)

        assert result.novel_id == novel_id
        assert result.autosave_interval == 60
        assert result.ai_provider == "anthropic"

    async def test_get_without_existing_settings_creates_defaults(
        self, project_settings_repo: FakeProjectSettingsRepository
    ) -> None:
        novel_id = uuid.uuid4()

        result = await project_settings_repo.get(novel_id)

        assert result.novel_id == novel_id
        assert result.autosave_interval == 30
        assert result.default_language == "en"
        assert result.ai_provider == ""
        assert result.model_overrides == "{}"

    async def test_get_records_call(
        self, project_settings_repo: FakeProjectSettingsRepository
    ) -> None:
        novel_id = uuid.uuid4()
        await project_settings_repo.get(novel_id)
        assert len(project_settings_repo.calls) == 1
        assert project_settings_repo.calls[0].method == "get"


class TestProjectSettingsUpdate:
    async def test_update_creates_settings_when_missing(
        self, project_settings_repo: FakeProjectSettingsRepository
    ) -> None:
        novel_id = uuid.uuid4()
        request = UpdateProjectSettingsRequest(
            autosave_interval=120, ai_provider="openai", ai_model="gpt-4o"
        )

        result = await project_settings_repo.update(novel_id, request)

        assert result.autosave_interval == 120
        assert result.ai_provider == "openai"
        assert result.ai_model == "gpt-4o"

    async def test_update_modifies_existing_settings(
        self, project_settings_repo: FakeProjectSettingsRepository
    ) -> None:
        novel_id = uuid.uuid4()
        settings = ProjectSettings()
        settings.novel_id = novel_id
        settings.autosave_interval = 30
        settings.default_language = "en"
        settings.ai_provider = "anthropic"
        settings.ai_model = "claude-3"
        settings.model_overrides = "{}"
        settings.updated_at = datetime.now(UTC)
        project_settings_repo.seed(settings)

        request = UpdateProjectSettingsRequest(autosave_interval=60, default_language="fr")
        result = await project_settings_repo.update(novel_id, request)

        assert result.autosave_interval == 60
        assert result.default_language == "fr"
        assert result.ai_provider == "anthropic"  # unchanged
        assert result.ai_model == "claude-3"  # unchanged

    async def test_update_records_call(
        self, project_settings_repo: FakeProjectSettingsRepository
    ) -> None:
        novel_id = uuid.uuid4()
        await project_settings_repo.update(
            novel_id, UpdateProjectSettingsRequest(autosave_interval=10)
        )
        assert any(c.method == "update" for c in project_settings_repo.calls)


# ======================================================================
# Schema validation tests
# ======================================================================


class TestUpdateUserSettingsRequestValidation:
    def test_valid_request_with_all_fields(self) -> None:
        req = UpdateUserSettingsRequest(display_name="Alice", ui_language="de", theme="dark")
        assert req.display_name == "Alice"
        assert req.ui_language == "de"
        assert req.theme == "dark"

    def test_valid_request_with_partial_fields(self) -> None:
        req = UpdateUserSettingsRequest(theme="light")
        assert req.display_name is None
        assert req.ui_language is None
        assert req.theme == "light"

    def test_invalid_theme_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(theme="neon")

    def test_display_name_max_length_100(self) -> None:
        name = "A" * 100
        req = UpdateUserSettingsRequest(display_name=name)
        assert req.display_name == name

    def test_display_name_too_long_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(display_name="A" * 101)

    def test_ui_language_too_short_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(ui_language="x")

    def test_ui_language_too_long_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            UpdateUserSettingsRequest(ui_language="a" * 11)


class TestUpdateProjectSettingsRequestValidation:
    def test_valid_request_with_all_fields(self) -> None:
        req = UpdateProjectSettingsRequest(
            autosave_interval=60,
            default_language="fr",
            ai_provider="anthropic",
            ai_model="claude-3",
            model_overrides='{"write": "claude-3"}',
        )
        assert req.autosave_interval == 60
        assert req.default_language == "fr"

    def test_autosave_interval_minimum_zero(self) -> None:
        req = UpdateProjectSettingsRequest(autosave_interval=0)
        assert req.autosave_interval == 0

    def test_autosave_interval_negative_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            UpdateProjectSettingsRequest(autosave_interval=-1)

    def test_autosave_interval_maximum_3600(self) -> None:
        req = UpdateProjectSettingsRequest(autosave_interval=3600)
        assert req.autosave_interval == 3600

    def test_autosave_interval_over_max_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            UpdateProjectSettingsRequest(autosave_interval=3601)


class TestUserSettingsResponseFields:
    """Verify response schema field definitions match expected types."""

    def test_user_settings_response_has_expected_fields(self) -> None:
        fields = UserSettingsResponse.model_fields
        assert "user_id" in fields
        assert "display_name" in fields
        assert "ui_language" in fields
        assert "theme" in fields
        assert "updated_at" in fields


class TestProjectSettingsResponseFields:
    def test_project_settings_response_has_expected_fields(self) -> None:
        fields = ProjectSettingsResponse.model_fields
        assert "novel_id" in fields
        assert "autosave_interval" in fields
        assert "default_language" in fields
        assert "ai_provider" in fields
        assert "ai_model" in fields
        assert "model_overrides" in fields
        assert "updated_at" in fields
