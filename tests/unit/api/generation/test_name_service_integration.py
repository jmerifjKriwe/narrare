"""Registry/composer integration and prompt-building tests for NameGeneratorService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from narrare.generation.name_service import NameGeneratorService
from narrare.generation.schemas import GenderEnum, NameType
from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.prompts.composer import PromptComposer

if TYPE_CHECKING:
    from tests.fakes.fake_llm_gateway import FakeModelRegistry

from .conftest import (
    SAMPLE_ARRAY_RESPONSE,
    _default_request,
    _make_config,
)

# ---------------------------------------------------------------------------
# _build_user_prompt — uses spec'd mocks (RULE-04 / no bare MagicMock)
# ---------------------------------------------------------------------------


class TestBuildUserPrompt:
    """Tests for the _build_user_prompt helper method."""

    @staticmethod
    def _make_prompt_service() -> NameGeneratorService:
        """Create a service with spec'd mocks for prompt-only tests."""
        return NameGeneratorService(
            registry=MagicMock(spec=ModelRegistry),
            composer=MagicMock(spec=PromptComposer),
            config=_make_config(),
        )

    def test_includes_count(self) -> None:
        svc = self._make_prompt_service()
        request = _default_request(count=10)
        prompt = svc._build_user_prompt(request)
        assert "10" in prompt

    def test_includes_name_type(self) -> None:
        svc = self._make_prompt_service()
        request = _default_request(name_type=NameType.PLACE)
        prompt = svc._build_user_prompt(request)
        assert "place" in prompt

    def test_includes_name_style(self) -> None:
        svc = self._make_prompt_service()
        request = _default_request(name_style="norse")
        prompt = svc._build_user_prompt(request)
        assert "norse" in prompt

    def test_includes_gender(self) -> None:
        svc = self._make_prompt_service()
        request = _default_request(gender=GenderEnum.FEMALE)
        prompt = svc._build_user_prompt(request)
        assert "female" in prompt

    def test_includes_explanation_language(self) -> None:
        svc = self._make_prompt_service()
        request = _default_request(explanation_language="fr")
        prompt = svc._build_user_prompt(request)
        assert "fr" in prompt

    def test_includes_json_format_instruction(self) -> None:
        svc = self._make_prompt_service()
        request = _default_request()
        prompt = svc._build_user_prompt(request)
        assert "JSON" in prompt
        assert "name" in prompt
        assert "pronunciation" in prompt
        assert "meaning" in prompt


# ---------------------------------------------------------------------------
# Registry / Composer integration
# ---------------------------------------------------------------------------


class TestRegistryAndComposerIntegration:
    """Verify the service calls registry and composer with correct arguments."""

    async def test_calls_composer_with_name_generate_intent(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
    ) -> None:
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        await service.generate_names(_default_request())

        mock_composer.build.assert_awaited_once()
        call_kwargs = mock_composer.build.call_args
        assert call_kwargs[0][0] == LLMIntent.NAME_GENERATE

    async def test_calls_composer_with_user_prompt(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
    ) -> None:
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        request = _default_request(name_style="celtic", count=3)
        await service.generate_names(request)

        call_kwargs = mock_composer.build.call_args
        user_prompt = call_kwargs.kwargs.get("user_prompt", call_kwargs[1].get("user_prompt", ""))
        assert "celtic" in user_prompt
        assert "3" in user_prompt

    async def test_calls_registry_with_name_generate_intent(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        await service.generate_names(_default_request())

        fake_registry.assert_called_with_intent(LLMIntent.NAME_GENERATE)

    async def test_calls_registry_once(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        await service.generate_names(_default_request())

        fake_registry.assert_called_once()

    async def test_passes_config_to_registry(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        await service.generate_names(_default_request())

        call = fake_registry.last_call()
        assert call.config == config

    async def test_composer_context_includes_request_params(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
    ) -> None:
        """PromptContext passed to composer should include culture, name_type, etc."""
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        request = _default_request(
            name_style="japanese",
            name_type=NameType.PLACE,
            count=3,
            gender=GenderEnum.MALE,
            explanation_language="ja",
        )
        await service.generate_names(request)

        # Inspect the PromptContext passed to composer.build()
        call_args = mock_composer.build.call_args
        context = call_args[0][1]  # second positional arg is PromptContext
        assert context.language == "ja"
        assert context.mode == "names"
        assert context.extra["name_style"] == "japanese"
        assert context.extra["name_type"] == "place"
        assert context.extra["count"] == "3"
        assert context.extra["gender"] == "male"
