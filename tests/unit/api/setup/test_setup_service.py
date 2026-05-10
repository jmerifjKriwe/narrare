"""Unit tests for setup/service.py"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from narrare.setup.schemas import (
    AIProvider,
    StarterContent,
    Step1LocationRequest,
    Step2NovelRequest,
    Step3StarterRequest,
    Step4ProviderRequest,
)
from narrare.setup.service import SetupService


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def service(mock_session: MagicMock) -> SetupService:
    svc = SetupService(mock_session)
    svc._provider_service = MagicMock()  # type: ignore[reportPrivateUsage]
    svc._demo_loader = MagicMock()  # type: ignore[reportPrivateUsage]
    return svc


class TestValidateStep1:
    async def test_valid_request_returns_response(self, service: SetupService) -> None:
        req = Step1LocationRequest(project_name="My Project", language="en")
        result = await service.validate_step1(req)
        assert result.valid is True
        assert result.project_name == "My Project"

    async def test_unsupported_language_raises_422(self, service: SetupService) -> None:
        req = Step1LocationRequest(project_name="Project", language="ja")
        with pytest.raises(HTTPException) as exc:
            await service.validate_step1(req)
        assert exc.value.status_code == 422
        assert "ja" in exc.value.detail

    async def test_supported_languages_accepted(self, service: SetupService) -> None:
        for lang in ("en", "de", "fr"):
            req = Step1LocationRequest(project_name="Project", language=lang)
            result = await service.validate_step1(req)
            assert result.valid is True


class TestValidateStep2:
    async def test_valid_novel_request(self, service: SetupService) -> None:
        req = Step2NovelRequest(title="My Fantasy Novel", genre="fantasy")
        result = await service.validate_step2(req)
        assert result.valid is True
        assert result.title == "My Fantasy Novel"


class TestValidateStep3:
    async def test_blank_starter_valid(self, service: SetupService) -> None:
        req = Step3StarterRequest(starter=StarterContent.BLANK)
        result = await service.validate_step3(req)
        assert result.valid is True
        assert result.demo_info is None

    async def test_demo_starter_returns_info(self, service: SetupService) -> None:
        from narrare.setup.schemas import DemoProjectInfo

        mock_info = DemoProjectInfo(
            id=StarterContent.DEMO_GERMAN,
            title="Im stillen Wald",
            language="de",
            genre="Literarische Fiktion",
            chapter_count=2,
            character_count=3,
            word_count=2660,
            description="Test description",
        )
        service._demo_loader.get_info = MagicMock(return_value=mock_info)  # type: ignore[reportPrivateUsage]
        req = Step3StarterRequest(starter=StarterContent.DEMO_GERMAN)
        result = await service.validate_step3(req)
        assert result.valid is True
        assert result.demo_info is not None
        assert result.demo_info.title == "Im stillen Wald"

    async def test_import_without_path_raises_422(self, service: SetupService) -> None:
        req = Step3StarterRequest(starter=StarterContent.IMPORT, import_path=None)
        with pytest.raises(HTTPException) as exc:
            await service.validate_step3(req)
        assert exc.value.status_code == 422

    async def test_import_nonexistent_path_raises_422(self, service: SetupService) -> None:
        req = Step3StarterRequest(
            starter=StarterContent.IMPORT,
            import_path="/definitely/does/not/exist",
        )
        with pytest.raises(HTTPException) as exc:
            await service.validate_step3(req)
        assert exc.value.status_code == 422


class TestValidateStep4:
    async def test_valid_provider_returns_response(self, service: SetupService) -> None:
        service._provider_service.validate_connection = AsyncMock(return_value=True)  # type: ignore[reportPrivateUsage]
        req = Step4ProviderRequest(
            provider=AIProvider.ANTHROPIC,
            api_key="sk-ant-test",
            model="claude-haiku-3-5-20241022",
        )
        result = await service.validate_step4(req)
        assert result.valid is True

    async def test_failed_connection_raises_422(self, service: SetupService) -> None:
        service._provider_service.validate_connection = AsyncMock(return_value=False)  # type: ignore[reportPrivateUsage]
        req = Step4ProviderRequest(
            provider=AIProvider.ANTHROPIC,
            api_key="bad-key",
            model="claude-haiku-3-5-20241022",
        )
        with pytest.raises(HTTPException) as exc:
            await service.validate_step4(req)
        assert exc.value.status_code == 422

    async def test_missing_api_key_raises_422(self, service: SetupService) -> None:
        req = Step4ProviderRequest(
            provider=AIProvider.ANTHROPIC,
            api_key="",
            model="claude-haiku-3-5-20241022",
        )
        with pytest.raises(HTTPException) as exc:
            await service.validate_step4(req)
        assert exc.value.status_code == 422

    async def test_ollama_skips_api_key_check(self, service: SetupService) -> None:
        service._provider_service.validate_connection = AsyncMock(return_value=True)  # type: ignore[reportPrivateUsage]
        req = Step4ProviderRequest(
            provider=AIProvider.OLLAMA,
            api_key="",  # Ollama has no key
            model="llama3.2",
            ollama_url="http://localhost:11434",
        )
        result = await service.validate_step4(req)
        assert result.valid is True
