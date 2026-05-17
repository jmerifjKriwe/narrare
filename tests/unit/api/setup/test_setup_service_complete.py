"""Unit tests for setup/service.complete() — core business logic."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare.setup.schemas import (
    CompleteSetupResponse,
    StarterContent,
)

from ._complete_helpers import (
    _make_service,
    _make_wizard_state,
)

if TYPE_CHECKING:
    from narrare.setup.service import SetupService
    from tests.fakes import FakeDemoLoader, FakeProviderService


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
        )

        await complete_service.complete(user_id, state)

        add_calls = complete_service._session.add.call_args_list  # pyright: ignore[reportAttributeAccessIssue]
        # Second add call should be ProjectSettings
        project_settings = add_calls[1][0][0]
        assert project_settings.autosave_interval == 60
        assert project_settings.default_language == "de"

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
        assert result.redirect_to == f"/novel/{result.novel_id}"
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

        assert result.redirect_to == f"/novel/{result.novel_id}"
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

        assert result.redirect_to == f"/novel/{result.novel_id}"
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
