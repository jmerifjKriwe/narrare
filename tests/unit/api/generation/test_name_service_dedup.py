"""Tests for KB dedup integration in NameGeneratorService — duplicate matching.

Verifies that:
- Names not in the KB remain unflagged
- Names present in the KB are flagged as duplicates
- Matching is case-insensitive and whitespace-trimmed
- An empty KB produces no flags
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

from ._ownership_fakes import permissive_novel_repo
from .conftest import _static_resolution


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


class TestNoKBRepo:
    async def test_no_kb_repo_all_false(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(json_names([{"name": "Aelindra", "meaning": "starlight"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            model_resolution=_static_resolution(config),
            novel_repo=permissive_novel_repo(),
        )
        result = await service.generate_names(_default_request(), user_id=uuid.uuid4())

        assert len(result.names) == 1
        assert result.names[0].is_duplicate is False


class TestNoDuplicates:
    async def test_no_match_all_false(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(json_names([{"name": "Elsa", "meaning": "oath"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            model_resolution=_static_resolution(config),
            novel_repo=permissive_novel_repo(),
            kb_repo=kb_repo([_FakeKBEntry("Anna", "character")]),
        )
        result = await service.generate_names(_default_request(), user_id=uuid.uuid4())

        assert len(result.names) == 1
        assert result.names[0].is_duplicate is False

    async def test_multiple_names_none_match(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(
            json_names(
                [
                    {"name": "Aelindra", "meaning": "starlight"},
                    {"name": "Theron", "meaning": "hunter"},
                ]
            )
        )

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            model_resolution=_static_resolution(config),
            novel_repo=permissive_novel_repo(),
            kb_repo=kb_repo(
                [
                    _FakeKBEntry("Anna", "character"),
                    _FakeKBEntry("Elsa", "character"),
                ]
            ),
        )
        result = await service.generate_names(_default_request(), user_id=uuid.uuid4())

        assert all(not n.is_duplicate for n in result.names)


class TestExactDuplicates:
    async def test_matching_name_flagged(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(
            json_names(
                [
                    {"name": "Anna", "meaning": "grace"},
                    {"name": "Elsa", "meaning": "oath"},
                ]
            )
        )

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            model_resolution=_static_resolution(config),
            novel_repo=permissive_novel_repo(),
            kb_repo=kb_repo([_FakeKBEntry("Anna", "character")]),
        )
        result = await service.generate_names(_default_request(), user_id=uuid.uuid4())

        anna = next(n for n in result.names if n.name == "Anna")
        elsa = next(n for n in result.names if n.name == "Elsa")
        assert anna.is_duplicate is True
        assert elsa.is_duplicate is False


class TestCaseInsensitiveMatching:
    async def test_lowercased_match(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(json_names([{"name": "anna", "meaning": "grace"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            model_resolution=_static_resolution(config),
            novel_repo=permissive_novel_repo(),
            kb_repo=kb_repo([_FakeKBEntry("Anna", "character")]),
        )
        result = await service.generate_names(_default_request(), user_id=uuid.uuid4())

        assert result.names[0].is_duplicate is True

    async def test_uppercased_match(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(json_names([{"name": "ANNA", "meaning": "grace"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            model_resolution=_static_resolution(config),
            novel_repo=permissive_novel_repo(),
            kb_repo=kb_repo([_FakeKBEntry("anna", "character")]),
        )
        result = await service.generate_names(_default_request(), user_id=uuid.uuid4())

        assert result.names[0].is_duplicate is True

    async def test_whitespace_trimmed(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(json_names([{"name": " Anna ", "meaning": "grace"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            model_resolution=_static_resolution(config),
            novel_repo=permissive_novel_repo(),
            kb_repo=kb_repo([_FakeKBEntry("  Anna  ", "character")]),
        )
        result = await service.generate_names(_default_request(), user_id=uuid.uuid4())

        assert result.names[0].is_duplicate is True


class TestEmptyKB:
    async def test_empty_kb_no_flags(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        fake_registry.returns(
            json_names(
                [
                    {"name": "Aelindra", "meaning": "starlight"},
                    {"name": "Theron", "meaning": "hunter"},
                ]
            )
        )

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            model_resolution=_static_resolution(config),
            novel_repo=permissive_novel_repo(),
            kb_repo=kb_repo([]),
        )
        result = await service.generate_names(_default_request(), user_id=uuid.uuid4())

        assert all(not n.is_duplicate for n in result.names)
