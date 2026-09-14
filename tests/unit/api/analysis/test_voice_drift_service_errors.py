"""Error + lazy-resolution tests for CharacterVoiceDriftService (ANAL-009).

Split from ``test_voice_drift_service.py`` for RULE-04 compliance (test
file hard limit 400 — the ADR-086 L11 additions crossed it). Covers the
failure modes the happy-path file does not, plus the lazy model-resolution
semantics at the service boundary:

- Novel not found / inaccessible -> NotFoundError.
- Unconfigured provider (routing cascade) -> ConfigurationError propagates
  un-swallowed from the entry point (ADR-086 lazy resolution).
- No PromptComposer -> ConfigurationError.
- Lazy resolution: never at construction, exactly once at first use,
  idempotent afterwards.

Mirrors ``test_author_voice_drift_service_errors.py`` (ADR-086 L10
precedent). See:

- ADR-073 (read-only longitudinal drift pipeline, ANAL-009)
- ADR-086 (lazy model resolution via ModelResolution)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare.analysis.schemas_voice_drift import VoiceDriftRequest
from narrare.analysis.voice_drift_service import CharacterVoiceDriftService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.shared.errors import ConfigurationError, NotFoundError
from tests.unit.api.analysis._voice_drift_test_helpers import (
    CHAPTER_ONE_DIALOGUE,
    CHAPTER_TWO_DIALOGUE,
    FakeChapterRepository,
    FakeModelRegistry,
    FakeNovelRepository,
    FakeVoiceProfileConsumer,
    _CountingResolution,
    _resolved_model,
    consume,
    make_chapter,
    make_drift_result,
    make_novel,
    make_profile,
    make_service,
    patch_mode1,
)

if TYPE_CHECKING:
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


def _two_chapters(novel_id: uuid.UUID) -> list[object]:
    return [
        make_chapter(novel_id=novel_id, title="Chapter 1", content=CHAPTER_ONE_DIALOGUE),
        make_chapter(novel_id=novel_id, title="Chapter 2", content=CHAPTER_TWO_DIALOGUE),
    ]


class TestVoiceDriftErrors:
    """Missing novel / unconfigured provider / composer raise typed errors (RULE-11)."""

    @pytest.mark.asyncio
    async def test_missing_novel_raises_not_found(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        consumer = FakeVoiceProfileConsumer([])
        service = make_service(novel=None, chapters=[], consumer=consumer, config=config)

        with pytest.raises(NotFoundError):
            await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

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
        consumer = FakeVoiceProfileConsumer([])
        service = make_service(
            novel=novel,
            chapters=[],
            consumer=consumer,
            config=config,
            model_resolution=_RaisingResolution(),
        )

        with pytest.raises(ConfigurationError):
            await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

    @pytest.mark.asyncio
    async def test_missing_composer_raises_configuration_error(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """No PromptComposer → ConfigurationError (resolution is set so it's
        the next guard that fires)."""
        novel = make_novel()
        service = CharacterVoiceDriftService(
            novel_repo=cast("NovelRepository", FakeNovelRepository(novel)),
            chapter_repo=cast("ChapterRepository", FakeChapterRepository([])),
            model_registry=cast("ModelRegistry", FakeModelRegistry()),
            consumer_provider=AsyncMock(),
            model_resolution=StaticModelResolution(_resolved_model(config)),
            composer=None,
        )

        with pytest.raises(ConfigurationError):
            await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))


# ---------------------------------------------------------------------------
# ADR-086: lazy model resolution at the service boundary
# ---------------------------------------------------------------------------


class TestLazyModelResolution:
    """ADR-086 lazy semantics at the service boundary.

    The DI factory runs pre-body-validation (FastAPI solves all
    sub-dependencies first), so the service must NOT resolve at
    construction. The first ``ensure_resolved()`` / ``run_stream()``
    resolves exactly once; repeat calls reuse the cached triple.
    """

    @pytest.mark.asyncio
    async def test_no_resolution_at_construction(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        resolution = _CountingResolution()
        make_service(
            novel=make_novel(),
            chapters=[],
            consumer=FakeVoiceProfileConsumer([]),
            config=config,
            model_resolution=resolution,
        )
        assert resolution.calls == 0

    @pytest.mark.asyncio
    async def test_ensure_resolved_resolves_once_and_is_idempotent(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        resolution = _CountingResolution()
        service = make_service(
            novel=make_novel(),
            chapters=[],
            consumer=FakeVoiceProfileConsumer([]),
            config=config,
            model_resolution=resolution,
        )

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert resolution.calls == 1
        assert first is second

    @pytest.mark.asyncio
    async def test_run_stream_resolves_lazily_on_first_use(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        resolution = _CountingResolution()
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(
            novel=novel,
            chapters=chapters,
            consumer=consumer,
            config=config,
            model_resolution=resolution,
        )

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

        assert resolution.calls == 1

    @pytest.mark.asyncio
    async def test_run_stream_after_ensure_resolved_reuses_cache(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        resolution = _CountingResolution()
        novel = make_novel()
        chapters = _two_chapters(novel.id)
        consumer = FakeVoiceProfileConsumer([make_profile("Elena")])
        service = make_service(
            novel=novel,
            chapters=chapters,
            consumer=consumer,
            config=config,
            model_resolution=resolution,
        )

        await service.ensure_resolved()

        with patch_mode1() as (MockAgent, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            MockAgent.return_value = mock_agent

            await consume(service.run_stream(novel.id, uuid.uuid4(), VoiceDriftRequest()))

        assert resolution.calls == 1
