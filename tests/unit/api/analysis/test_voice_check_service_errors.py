"""Error-handling tests for CharacterVoiceCheckerService.

Covers the failure modes the happy-path file does not:

- Chapter/novel not found → NotFoundError.
- Unconfigured provider (routing cascade) → ConfigurationError propagates
  un-swallowed from the entry point (ADR-086 lazy resolution).
- No PromptComposer → ConfigurationError.
- Agent failure propagates (no silent swallow).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.shared.errors import ConfigurationError
from tests.unit.api.analysis._voice_check_test_helpers import (
    FakeComposer,
    FakeVoiceProfileConsumer,
    consume,
    make_chapter,
    make_novel,
    make_profile,
    make_service,
    patch_mode1,
)

if TYPE_CHECKING:
    from narrare_core.llm.model_routing import ResolvedModel


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


class TestVoiceCheckErrors:
    """Errors propagate or convert to typed domain errors; never swallowed."""

    @pytest.mark.asyncio
    async def test_missing_chapter_raises_not_found(self, config: ResolvedModelConfig) -> None:
        from narrare_core.shared.errors import NotFoundError

        novel = make_novel()
        consumer = FakeVoiceProfileConsumer([])
        service = make_service(novel=novel, chapter=None, consumer=consumer, config=config)

        with pytest.raises(NotFoundError):
            await consume(service.check(uuid.uuid4(), uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_missing_novel_raises_not_found(self, config: ResolvedModelConfig) -> None:
        from narrare_core.shared.errors import NotFoundError

        chapter = make_chapter()
        consumer = FakeVoiceProfileConsumer([])
        service = make_service(novel=None, chapter=chapter, consumer=consumer, config=config)

        with pytest.raises(NotFoundError):
            await consume(service.check(chapter.id, uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_missing_composer_raises_configuration_error(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare_core.shared.errors import ConfigurationError

        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(
            novel=novel,
            chapter=chapter,
            consumer=consumer,
            config=config,
            composer=FakeComposer(),
        )
        service._composer = None

        with pytest.raises(ConfigurationError):
            await consume(service.check(chapter.id, uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_resolver_configuration_error_propagates_un_swallowed(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """RULE-11 / ADR-086: the routing cascade's ConfigurationError
        (unconfigured provider) propagates from the entry point — the
        service never swallows it (AI-mandatory endpoint)."""

        class _RaisingResolution:
            async def resolve(self) -> ResolvedModel:
                raise ConfigurationError(
                    "No AI provider configured.",
                    code="NO_AI_PROVIDER",
                )

        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(
            novel=novel,
            chapter=chapter,
            consumer=consumer,
            config=config,
            model_resolution=_RaisingResolution(),
        )

        with pytest.raises(ConfigurationError):
            await consume(service.check(chapter.id, uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_agent_failure_propagates(self, config: ResolvedModelConfig) -> None:
        novel = make_novel()
        chapter = make_chapter(novel_id=novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(novel=novel, chapter=chapter, consumer=consumer, config=config)

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM blew up"))
            MockAgent.return_value = mock_agent

            with pytest.raises(RuntimeError, match="LLM blew up"):
                await consume(service.check(chapter.id, uuid.uuid4()))
