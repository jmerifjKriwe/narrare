"""Shared helpers and fakes for setup/service.complete() tests.

Private module (underscore prefix) — not collected by pytest.
Import from test files in this directory.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.setup.schemas import (
    AIProvider,
    StarterContent,
    StoryStructure,
    StoryTone,
    WizardState,
)
from narrare.setup.service import SetupService
from tests.fakes import FakeDemoLoader, FakeProviderService

if TYPE_CHECKING:
    from narrare.settings.schemas import UpdateUserSettingsRequest

__all__ = [
    "_make_mock_session",
    "_make_wizard_state",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_provider_service() -> FakeProviderService:
    return FakeProviderService()


@pytest.fixture
def fake_demo_loader() -> FakeDemoLoader:
    return FakeDemoLoader()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _make_mock_session() -> MagicMock:
    """Create a mocked AsyncSession for complete() tests."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.flush = AsyncMock()
    return mock_session


def _make_wizard_state(**overrides: object) -> WizardState:
    """Create a WizardState with sensible defaults."""
    defaults: dict[str, object] = {
        "project_name": "Test Project",
        "writing_language": "en",
        "autosave_interval": 30,
        "title": "Test Novel",
        "author": "Test Author",
        "genre": "fantasy",
        "logline": "A test logline",
        "story_structure": StoryStructure.THREE_ACT,
        "tone": StoryTone.DRAMATIC,
        "starter": StarterContent.BLANK,
        "provider": AIProvider.ANTHROPIC,
        "api_key": "sk-test-key",
        "model": "claude-haiku",
        "ollama_url": "http://localhost:11434",
        "zai_endpoint": "general",
    }
    defaults.update(overrides)
    return cast("Any", WizardState)(**defaults)


def _make_service(
    fake_provider_service: FakeProviderService,
    fake_demo_loader: FakeDemoLoader,
    mock_session: MagicMock | None = None,
    ai_settings_override: object | None = None,
) -> SetupService:
    """Create a SetupService with mocked dependencies."""
    return SetupService(
        session=mock_session or _make_mock_session(),
        novel_repo=None,  # pyright: ignore[reportArgumentType]
        user_settings_repo=_FakeUserSettingsRepo(),  # pyright: ignore[reportArgumentType]
        project_settings_repo=_FakeProjectSettingsRepo(),  # pyright: ignore[reportArgumentType]
        provider_service=fake_provider_service,
        demo_loader=fake_demo_loader,
        providers_repo=_FakeProvidersRepo(),  # pyright: ignore[reportArgumentType]
        ai_settings_repo=_FakeAiSettingsRepo(settings_override=ai_settings_override),  # pyright: ignore[reportArgumentType]
    )


@pytest.fixture
def complete_service(
    fake_provider_service: FakeProviderService, fake_demo_loader: FakeDemoLoader
) -> SetupService:
    """Service fixture with mocked session for complete() tests."""
    return _make_service(fake_provider_service, fake_demo_loader)


# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class _FakeUserSettingsRepo:
    """Minimal fake for UserSettingsRepositoryProtocol used by complete()."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def get(self, user_id: uuid.UUID) -> object:
        return object()

    async def update(self, user_id: uuid.UUID, request: UpdateUserSettingsRequest) -> object:
        self.calls.append({"method": "update", "user_id": user_id, "request": request})
        return object()


class _FakeProjectSettingsRepo:
    """Minimal fake for ProjectSettingsRepositoryProtocol used by complete()."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def get(self, novel_id: uuid.UUID) -> object:
        return object()

    async def update(self, novel_id: uuid.UUID, request: object) -> object:
        self.calls.append({"method": "update", "novel_id": novel_id})
        return object()


class _FakeProvidersRepo:
    """Minimal fake for UserProvidersRepository used by complete()."""

    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    async def create(
        self,
        user_id: uuid.UUID,
        provider_name: str,
        api_key_encrypted: str,
        base_url: str | None,
    ) -> object:
        provider_id = uuid.uuid4()
        self.created.append(
            {
                "user_id": user_id,
                "provider_name": provider_name,
                "api_key_encrypted": api_key_encrypted,
                "base_url": base_url,
                "id": provider_id,
            }
        )
        # Return a simple namespace object that has .id
        return type("Provider", (), {"id": provider_id})()


class _FakeAiSettingsRepo:
    """Minimal fake for UserAiSettingsRepository used by complete()."""

    def __init__(self, settings_override: object | None = None) -> None:
        self.updates: list[dict[str, object]] = []
        self._settings_override = settings_override

    async def get(self, user_id: uuid.UUID) -> object:
        if self._settings_override is not None:
            return self._settings_override
        return object()

    async def update(self, user_id: uuid.UUID, **kwargs: object) -> object:
        self.updates.append({"user_id": user_id, **kwargs})
        return object()
