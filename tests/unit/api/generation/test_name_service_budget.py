"""Tests for token-budget enforcement in NameGeneratorService.

Verifies that:
- Existing names are capped when the joined string exceeds the token budget.
- Short name lists pass through unchanged.
- The empty-list path (no KB repo) is unaffected.
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


def _long_names(count: int) -> list[_FakeKBEntry]:
    """Generate *count* fake KB entries with multi-word names.

    Each name is deliberately verbose to blow past the token budget
    with fewer entries.
    """
    return [
        _FakeKBEntry(
            f"Lord Aethon Brightblade the {i}th Conqueror of the Northern Realms",
            "character",
        )
        for i in range(count)
    ]


class TestNameServiceTokenBudget:
    """Token-budget enforcement for _fetch_existing_names."""

    async def test_existing_names_capped_when_exceeding_budget(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """200 verbose names should be truncated to fit the budget."""
        fake_registry.returns(json_names([{"name": "Zara", "meaning": "x"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            config=config,
            novel_repo=permissive_novel_repo(),
            kb_repo=kb_repo(_long_names(200)),
        )
        await service.generate_names(_default_request(), user_id=uuid.uuid4())

        context = mock_composer.build.call_args.args[1]
        existing: str = context.extra["existing_names"]
        # The capped string must be shorter than the unbounded one would be.
        # 200 * ~60 chars each = ~12 000 chars; the capped version must be
        # significantly less.
        assert len(existing) < 5000

    async def test_existing_names_not_capped_when_within_budget(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """A short list of names passes through unmodified."""
        fake_registry.returns(json_names([{"name": "Anna", "meaning": "grace"}]))

        entries = [
            _FakeKBEntry("Anna", "character"),
            _FakeKBEntry("Elsa", "character"),
            _FakeKBEntry("Olaf", "character"),
        ]
        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            config=config,
            novel_repo=permissive_novel_repo(),
            kb_repo=kb_repo(entries),
        )
        await service.generate_names(_default_request(), user_id=uuid.uuid4())

        context = mock_composer.build.call_args.args[1]
        existing: str = context.extra["existing_names"]
        assert "Anna" in existing
        assert "Elsa" in existing
        assert "Olaf" in existing

    async def test_existing_names_empty_when_no_kb_repo(
        self,
        fake_registry: FakeModelRegistry,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """No KB repo → empty existing_names (existing behaviour preserved)."""
        fake_registry.returns(json_names([{"name": "Anna", "meaning": "grace"}]))

        service = NameGeneratorService(
            registry=fake_registry,
            composer=mock_composer,
            config=config,
            novel_repo=permissive_novel_repo(),
        )
        await service.generate_names(_default_request(), user_id=uuid.uuid4())

        context = mock_composer.build.call_args.args[1]
        assert context.extra["existing_names"] == ""
