"""Error-handling / RULE-11 tests for CharacterVoiceService (ANAL-008).

Split from ``test_character_voice_service.py`` for RULE-04 compliance.
Verifies that errors propagate — the service never silently swallows them
(RULE-11).

See:
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-11 (no silent failures).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._character_voice_test_helpers import (
    FakeComposer,
    consume,
    make_chapter,
    make_novel,
    make_service,
    patch_mode1,
)

if TYPE_CHECKING:
    from narrare_core.llm.model_routing import ResolvedModel


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


class TestErrorHandling:
    """Errors propagate — the service never swallows them (RULE-11)."""

    @pytest.mark.asyncio
    async def test_novel_not_found_raises_not_found_error(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare_core.shared.errors import NotFoundError

        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[attr-defined]

        with pytest.raises(NotFoundError):
            await consume(service.analyze(uuid.uuid4(), None, uuid.uuid4()))  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_no_composer_raises_configuration_error(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare_core.shared.errors import ConfigurationError

        service = make_service(FakeComposer(), config)
        service._composer = None  # type: ignore[assignment]
        service._novel_repo.get_by_id = AsyncMock(return_value=make_novel())  # type: ignore[attr-defined]

        with pytest.raises(ConfigurationError):
            await consume(service.analyze(uuid.uuid4(), None, uuid.uuid4()))  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_resolver_configuration_error_propagates_un_swallowed(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """RULE-11 / ADR-086: the routing cascade's ConfigurationError
        (unconfigured provider) propagates from the entry point — the
        service never swallows it (AI-mandatory endpoint)."""
        from narrare_core.shared.errors import ConfigurationError

        class _RaisingResolution:
            async def resolve(self) -> ResolvedModel:
                raise ConfigurationError(
                    "No AI provider configured.",
                    code="NO_AI_PROVIDER",
                )

        service = make_service(
            composer,
            config,
            model_resolution=_RaisingResolution(),
        )

        with pytest.raises(ConfigurationError):
            await consume(service.analyze(uuid.uuid4(), None, uuid.uuid4()))  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_selected_chapter_not_found_raises_not_found_error(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare_core.shared.errors import NotFoundError

        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=make_novel())  # type: ignore[attr-defined]
        service._chapter_repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[attr-defined]

        with pytest.raises(NotFoundError):
            await consume(service.analyze(uuid.uuid4(), [uuid.uuid4()], uuid.uuid4()))  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_agent_failure_propagates(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """RULE-11: an agent failure must propagate, not be swallowed."""
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)

        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=[chapter])  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM blew up"))
            MockAgent.return_value = mock_agent

            with pytest.raises(RuntimeError, match="LLM blew up"):
                await consume(service.analyze(novel.id, None, uuid.uuid4()))  # type: ignore[arg-type]
