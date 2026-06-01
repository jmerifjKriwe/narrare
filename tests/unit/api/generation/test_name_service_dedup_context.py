"""Tests for KB dedup — existing_names in prompt context and entity type filtering.

Verifies that:
- existing_names are populated in the prompt context for proactive dedup
- existing_names is empty when no KB repo is configured
- KB names are filtered by entity type matching the requested NameType
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from narrare_core.llm import ResolvedModelConfig
    from tests.fakes.fake_llm_gateway import FakeModelRegistry

from narrare.generation.name_service import NameGeneratorService
from narrare.generation.schemas import (
    GenderEnum,
    NameGenerateRequest,
    NameType,
)
from tests.unit.api.generation._dedup_fakes import (
    _FakeKBEntry,
    json_names,
    kb_repo,
)


def _default_request(**overrides: Any) -> NameGenerateRequest:
    defaults: dict[str, Any] = {
        "project_id": uuid.uuid4(),
        "name_type": NameType.CHARACTER,
        "name_style": "fantasy",
        "count": 5,
        "gender": GenderEnum.ANY,
        "explanation_language": "en",
    }
    defaults.update(overrides)
    return NameGenerateRequest(**defaults)


class TestExistingNamesInPrompt:
    async def test_existing_names_populated_from_kb(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(json_names([{"name": "Olaf", "meaning": "fun"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            config=config,
            kb_repo=kb_repo(
                [
                    _FakeKBEntry("Anna", "character"),
                    _FakeKBEntry("Elsa", "character"),
                ]
            ),
        )
        await service.generate_names(_default_request())

        context = mock_composer.build.call_args.args[1]
        existing = context.extra["existing_names"]
        assert "Anna" in existing
        assert "Elsa" in existing

    async def test_existing_names_empty_when_no_kb(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(json_names([{"name": "Olaf", "meaning": "fun"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            config=config,
        )
        await service.generate_names(_default_request())

        context = mock_composer.build.call_args.args[1]
        assert context.extra["existing_names"] == ""

    async def test_existing_names_comma_separated(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(json_names([{"name": "Sven", "meaning": "lad"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            config=config,
            kb_repo=kb_repo(
                [
                    _FakeKBEntry("Anna", "character"),
                    _FakeKBEntry("Elsa", "character"),
                    _FakeKBEntry("Olaf", "character"),
                ]
            ),
        )
        await service.generate_names(_default_request())

        context = mock_composer.build.call_args.args[1]
        existing = context.extra["existing_names"]
        parts = [p.strip() for p in existing.split(",")]
        assert len(parts) == 3
        assert "Anna" in parts
        assert "Elsa" in parts
        assert "Olaf" in parts


class TestEntityTypeFiltering:
    async def test_character_names_only_check_characters(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(
            json_names(
                [
                    {"name": "Anna", "meaning": "grace"},
                    {"name": "Thornhaven", "meaning": "fortress"},
                ]
            )
        )

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            config=config,
            kb_repo=kb_repo(
                [
                    _FakeKBEntry("Anna", "character"),
                    _FakeKBEntry("Thornhaven", "location"),
                ]
            ),
        )
        result = await service.generate_names(_default_request(name_type=NameType.CHARACTER))

        anna = next(n for n in result.names if n.name == "Anna")
        thornhaven = next(n for n in result.names if n.name == "Thornhaven")
        assert anna.is_duplicate is True
        assert thornhaven.is_duplicate is False

    async def test_place_names_only_check_locations(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(
            json_names(
                [
                    {"name": "Thornhaven", "meaning": "fortress"},
                    {"name": "Anna", "meaning": "grace"},
                ]
            )
        )

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            config=config,
            kb_repo=kb_repo(
                [
                    _FakeKBEntry("Anna", "character"),
                    _FakeKBEntry("Thornhaven", "location"),
                ]
            ),
        )
        result = await service.generate_names(_default_request(name_type=NameType.PLACE))

        thornhaven = next(n for n in result.names if n.name == "Thornhaven")
        anna = next(n for n in result.names if n.name == "Anna")
        assert thornhaven.is_duplicate is True
        assert anna.is_duplicate is False

    async def test_existing_names_filtered_by_type_for_prompt(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(json_names([{"name": "NewPlace", "meaning": "settlement"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            config=config,
            kb_repo=kb_repo(
                [
                    _FakeKBEntry("Anna", "character"),
                    _FakeKBEntry("Thornhaven", "location"),
                ]
            ),
        )
        await service.generate_names(_default_request(name_type=NameType.PLACE))

        context = mock_composer.build.call_args.args[1]
        existing = context.extra["existing_names"]
        assert "Thornhaven" in existing
        assert "Anna" not in existing
