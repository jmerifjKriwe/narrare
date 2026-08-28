"""Happy path and parameter variation tests for NameGeneratorService."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from narrare.generation.name_service import NameGeneratorService
from narrare.generation.schemas import GenderEnum, NameType
from tests.fakes.fake_llm_gateway import FakeModelRegistry

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from narrare_core.llm import ResolvedModelConfig

from ._ownership_fakes import permissive_novel_repo
from .conftest import (
    SAMPLE_ARRAY_RESPONSE,
    _default_request,
    _json_names_response,
)

# ---------------------------------------------------------------------------
# generate_names — Happy Path
# ---------------------------------------------------------------------------


class TestGenerateNamesHappyPath:
    """Tests for the main generate_names method — successful scenarios."""

    async def test_returns_response_with_names(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        """Full happy path: registry returns valid JSON → parsed into response."""
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        request = _default_request()
        result = await service.generate_names(request, user_id=uuid4())

        assert result.count == 3
        assert len(result.names) == 3
        assert result.name_style == "fantasy"
        assert result.name_type == "character"

    async def test_first_name_has_correct_fields(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        result = await service.generate_names(_default_request(), user_id=uuid4())
        first = result.names[0]

        assert first.name == "Aelindra"
        assert first.pronunciation == "ay-LIN-dra"
        assert first.meaning == "starlight"
        assert first.type == "character"
        assert first.name_style == "fantasy"

    async def test_names_without_pronunciation_get_none(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(
            _json_names_response(
                [
                    {"name": "Sera", "meaning": "light"},
                ]
            )
        )

        result = await service.generate_names(_default_request(), user_id=uuid4())
        assert result.names[0].pronunciation is None

    async def test_names_without_meaning_get_none(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(
            _json_names_response(
                [
                    {"name": "Vex"},
                ]
            )
        )

        result = await service.generate_names(_default_request(), user_id=uuid4())
        assert result.names[0].meaning is None

    async def test_passes_api_key_and_base_url_to_registry(
        self,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """Service forwards optional credentials to registry."""
        fake_reg = FakeModelRegistry()
        fake_reg.returns(SAMPLE_ARRAY_RESPONSE)

        svc = NameGeneratorService(
            registry=fake_reg,
            composer=mock_composer,
            config=config,
            novel_repo=permissive_novel_repo(),
            api_key="sk-test-key",
            base_url="https://custom.llm.api/v1",
        )

        await svc.generate_names(_default_request(), user_id=uuid4())

        call = fake_reg.last_call()
        assert call.api_key == "sk-test-key"
        assert call.base_url == "https://custom.llm.api/v1"


# ---------------------------------------------------------------------------
# generate_names — Different Parameter Combinations
# ---------------------------------------------------------------------------


class TestGenerateNamesParameters:
    """Verify service handles all name types, cultures, genders, languages."""

    async def test_place_names(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(
            _json_names_response([{"name": "Thornhaven", "meaning": "fortress of thorns"}])
        )

        result = await service.generate_names(
            _default_request(name_type=NameType.PLACE), user_id=uuid4()
        )

        assert result.name_type == "place"
        assert result.names[0].type == "place"

    async def test_organization_names(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(
            _json_names_response([{"name": "The Silver Covenant", "meaning": "order of mages"}])
        )

        result = await service.generate_names(
            _default_request(name_type=NameType.ORGANIZATION), user_id=uuid4()
        )

        assert result.name_type == "organization"

    async def test_item_names(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(
            _json_names_response([{"name": "Dawnbreaker", "meaning": "sword of light"}])
        )

        result = await service.generate_names(
            _default_request(name_type=NameType.ITEM), user_id=uuid4()
        )

        assert result.name_type == "item"
        assert result.names[0].type == "item"

    async def test_different_culture(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(
            _json_names_response([{"name": "Sakura", "meaning": "cherry blossom"}])
        )

        result = await service.generate_names(
            _default_request(name_style="japanese"), user_id=uuid4()
        )

        assert result.name_style == "japanese"
        assert result.names[0].name_style == "japanese"

    async def test_gender_male(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(_json_names_response([{"name": "Thorin", "meaning": "brave one"}]))

        result = await service.generate_names(
            _default_request(gender=GenderEnum.MALE), user_id=uuid4()
        )

        assert len(result.names) == 1

    async def test_gender_female(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(_json_names_response([{"name": "Elara", "meaning": "shining one"}]))

        result = await service.generate_names(
            _default_request(gender=GenderEnum.FEMALE), user_id=uuid4()
        )

        assert len(result.names) == 1

    async def test_gender_neutral(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(_json_names_response([{"name": "River", "meaning": "flowing water"}]))

        result = await service.generate_names(
            _default_request(gender=GenderEnum.NEUTRAL), user_id=uuid4()
        )

        assert len(result.names) == 1

    async def test_count_reflected_in_user_prompt(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
    ) -> None:
        fake_registry.returns(SAMPLE_ARRAY_RESPONSE)

        request = _default_request(count=20)
        await service.generate_names(request, user_id=uuid4())

        call_kwargs = mock_composer.build.call_args
        user_prompt = call_kwargs.kwargs.get("user_prompt", call_kwargs[1].get("user_prompt", ""))
        assert "20" in user_prompt

    async def test_language_de(
        self,
        service: NameGeneratorService,
        fake_registry: FakeModelRegistry,
    ) -> None:
        fake_registry.returns(
            _json_names_response([{"name": "Falkenstein", "meaning": "falcon stone"}])
        )

        result = await service.generate_names(
            _default_request(explanation_language="de"), user_id=uuid4()
        )

        assert len(result.names) == 1
