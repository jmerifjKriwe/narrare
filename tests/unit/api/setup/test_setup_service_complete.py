"""Unit tests for setup/service.complete() — business logic with Fake classes."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.setup.schemas import (
    AIProvider,
    CompleteSetupResponse,
    StarterContent,
    StoryStructure,
    StoryTone,
    WizardState,
)
from narrare.setup.service import SetupService
from tests.fakes import FakeDemoLoader, FakeProviderService

if TYPE_CHECKING:
    from narrare.settings.schemas import UpdateUserSettingsRequest


@pytest.fixture
def fake_provider_service() -> FakeProviderService:
    return FakeProviderService()


@pytest.fixture
def fake_demo_loader() -> FakeDemoLoader:
    return FakeDemoLoader()


def _make_mock_session() -> MagicMock:
    """Create a mocked AsyncSession for complete() tests."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.flush = AsyncMock()
    return mock_session


def _make_wizard_state(**overrides: object) -> WizardState:
    """Create a WizardState with sensible defaults."""
    defaults: dict[str, object] = {
        "project_name": "Test Project",
        "language": "en",
        "autosave_interval": 30,
        "title": "Test Novel",
        "author": "Test Author",
        "genre": "fantasy",
        "logline": "A test logline",
        "story_structure": StoryStructure.THREE_ACT,
        "tone": StoryTone.DRAMATIC,
        "starter": StarterContent.BLANK,
        "import_path": None,
        "provider": AIProvider.ANTHROPIC,
        "api_key": "sk-test-key",
        "model": "claude-haiku",
        "ollama_url": "http://localhost:11434",
    }
    defaults.update(overrides)
    return WizardState(**defaults)  # type: ignore[arg-type]


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


def _make_service(
    fake_provider_service: FakeProviderService,
    fake_demo_loader: FakeDemoLoader,
    mock_session: MagicMock | None = None,
) -> SetupService:
    """Create a SetupService with mocked dependencies."""
    return SetupService(
        session=mock_session or _make_mock_session(),
        novel_repo=None,  # type: ignore[arg-type]
        user_settings_repo=_FakeUserSettingsRepo(),  # type: ignore[arg-type]
        project_settings_repo=_FakeProjectSettingsRepo(),  # type: ignore[arg-type]
        provider_service=fake_provider_service,
        demo_loader=fake_demo_loader,
    )


@pytest.fixture
def complete_service(
    fake_provider_service: FakeProviderService, fake_demo_loader: FakeDemoLoader
) -> SetupService:
    """Service fixture with mocked session for complete() tests."""
    return _make_service(fake_provider_service, fake_demo_loader)


class TestComplete:
    async def test_complete_with_blank_starter_returns_response(
        self, complete_service: SetupService
    ) -> None:
        """Happy path: blank starter creates novel and settings."""
        user_id = str(uuid.uuid4())
        state = _make_wizard_state(starter=StarterContent.BLANK)

        result = await complete_service.complete(user_id, state)

        assert isinstance(result, CompleteSetupResponse)
        assert result.novel_id
        assert result.redirect_to == "/dashboard"
        assert "Setup complete" in result.message

    async def test_complete_creates_novel(self, complete_service: SetupService) -> None:
        """Verify a Novel is added to the session."""
        user_id = str(uuid.uuid4())
        state = _make_wizard_state(title="My Novel", genre="scifi")

        await complete_service.complete(user_id, state)

        # Session.add should have been called at least once (novel + project settings)
        assert complete_service._session.add.call_count >= 1  # pyright: ignore[reportAttributeAccessIssue]

        # Check the novel was created with correct attributes
        add_calls = complete_service._session.add.call_args_list  # pyright: ignore[reportAttributeAccessIssue]
        novel = add_calls[0][0][0]
        assert novel.title == "My Novel"
        assert novel.genre == "scifi"
        assert novel.language == "en"

    async def test_complete_creates_project_settings(self, complete_service: SetupService) -> None:
        """Verify ProjectSettings is created with correct values."""
        user_id = str(uuid.uuid4())
        state = _make_wizard_state(
            autosave_interval=60,
            language="de",
            provider=AIProvider.OPENAI,
            model="gpt-4o",
        )

        await complete_service.complete(user_id, state)

        add_calls = complete_service._session.add.call_args_list  # pyright: ignore[reportAttributeAccessIssue]
        # Second add call should be ProjectSettings
        project_settings = add_calls[1][0][0]
        assert project_settings.autosave_interval == 60
        assert project_settings.default_language == "de"
        assert project_settings.ai_provider == "openai"
        assert project_settings.ai_model == "gpt-4o"

    async def test_complete_updates_user_settings(self, complete_service: SetupService) -> None:
        """Verify user settings are updated with the selected language."""
        fake_user_repo = complete_service._user_settings_repo  # type: ignore[assignment]
        user_id = uuid.uuid4()
        state = _make_wizard_state(language="fr")

        await complete_service.complete(str(user_id), state)

        assert len(fake_user_repo.calls) == 1  # type: ignore[attr-defined]
        assert fake_user_repo.calls[0]["user_id"] == user_id  # type: ignore[attr-defined]
        assert fake_user_repo.calls[0]["request"].ui_language == "fr"  # type: ignore[attr-defined]

    async def test_complete_with_demo_fantasy_redirects_to_editor(
        self,
        fake_provider_service: FakeProviderService,
        fake_demo_loader: FakeDemoLoader,
    ) -> None:
        """Fantasy demo loads content and redirects to editor."""
        svc = _make_service(fake_provider_service, fake_demo_loader)

        user_id = str(uuid.uuid4())
        state = _make_wizard_state(starter=StarterContent.DEMO_FANTASY)

        result = await svc.complete(user_id, state)

        assert isinstance(result, CompleteSetupResponse)
        assert "/editor" in result.redirect_to
        # Demo loader.load should have been called
        load_calls = [c for c in fake_demo_loader.calls if c["method"] == "load"]
        assert len(load_calls) == 1
        assert load_calls[0]["starter"] == StarterContent.DEMO_FANTASY

    async def test_complete_with_demo_scifi_redirects_to_editor(
        self,
        fake_provider_service: FakeProviderService,
        fake_demo_loader: FakeDemoLoader,
    ) -> None:
        """SciFi demo loads content and redirects to editor."""
        svc = _make_service(fake_provider_service, fake_demo_loader)

        user_id = str(uuid.uuid4())
        state = _make_wizard_state(starter=StarterContent.DEMO_SCIFI)

        result = await svc.complete(user_id, state)

        assert "/editor" in result.redirect_to
        load_calls = [c for c in fake_demo_loader.calls if c["method"] == "load"]
        assert len(load_calls) == 1
        assert load_calls[0]["starter"] == StarterContent.DEMO_SCIFI

    async def test_complete_with_demo_german_redirects_to_editor(
        self,
        fake_provider_service: FakeProviderService,
        fake_demo_loader: FakeDemoLoader,
    ) -> None:
        """German demo loads content and redirects to editor."""
        svc = _make_service(fake_provider_service, fake_demo_loader)

        user_id = str(uuid.uuid4())
        state = _make_wizard_state(starter=StarterContent.DEMO_GERMAN, language="de")

        result = await svc.complete(user_id, state)

        assert "/editor" in result.redirect_to
        load_calls = [c for c in fake_demo_loader.calls if c["method"] == "load"]
        assert len(load_calls) == 1
        assert load_calls[0]["starter"] == StarterContent.DEMO_GERMAN

    async def test_complete_marks_demo_novel_as_is_demo(
        self, complete_service: SetupService
    ) -> None:
        """Novels created with demo starters have is_demo=True."""
        user_id = str(uuid.uuid4())
        state = _make_wizard_state(starter=StarterContent.DEMO_FANTASY)

        await complete_service.complete(user_id, state)

        add_calls = complete_service._session.add.call_args_list  # pyright: ignore[reportAttributeAccessIssue]
        novel = add_calls[0][0][0]
        assert novel.is_demo is True

    async def test_complete_blank_starter_is_not_demo(self, complete_service: SetupService) -> None:
        """Blank starter novels have is_demo=False."""
        user_id = str(uuid.uuid4())
        state = _make_wizard_state(starter=StarterContent.BLANK)

        await complete_service.complete(user_id, state)

        add_calls = complete_service._session.add.call_args_list  # pyright: ignore[reportAttributeAccessIssue]
        novel = add_calls[0][0][0]
        assert novel.is_demo is False

    async def test_complete_with_missing_demo_files_redirects_to_dashboard(
        self,
        fake_provider_service: FakeProviderService,
        fake_demo_loader: FakeDemoLoader,
    ) -> None:
        """When demo loader raises FileNotFoundError, redirect goes to dashboard."""
        from unittest.mock import AsyncMock

        # Make the demo loader raise FileNotFoundError on load
        async def raise_file_not_found(*args, **kwargs):
            raise FileNotFoundError("Demo files not found")

        fake_demo_loader.load = AsyncMock(side_effect=raise_file_not_found)  # type: ignore[method-assign]

        svc = _make_service(fake_provider_service, fake_demo_loader)

        user_id = str(uuid.uuid4())
        state = _make_wizard_state(starter=StarterContent.DEMO_FANTASY)

        result = await svc.complete(user_id, state)

        # Should gracefully fall back to dashboard
        assert result.redirect_to == "/dashboard"

    async def test_complete_flushes_session_twice(self, complete_service: SetupService) -> None:
        """Session.flush() is called twice: once after novel, once at the end."""
        user_id = str(uuid.uuid4())
        state = _make_wizard_state()

        await complete_service.complete(user_id, state)

        assert complete_service._session.flush.call_count == 2  # pyright: ignore[reportAttributeAccessIssue]
