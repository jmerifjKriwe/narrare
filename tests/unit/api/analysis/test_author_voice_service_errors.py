"""RULE-11 error-path tests for AuthorVoiceService (ANAL-007 / ADR-074).

Covers the failure modes the happy-path file does not:

- Novel not found / inaccessible → NotFoundError.
- Unconfigured provider (routing cascade) → ConfigurationError propagates
  un-swallowed from the entry point (ADR-086 lazy resolution).
- No PromptComposer → ConfigurationError.
- Agent failure propagates (no silent swallow).
- get_profile / clear_profile enforce novel access control.

Mirrors ``test_character_voice_service_errors.py`` (ADR-055 precedent).

See:
    ADR-074 — Author Voice Storage Contract.
    CONSTRAINTS.md RULE-11 (no silent failures).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.shared.errors import ConfigurationError, NotFoundError
from tests.unit.api.analysis._author_voice_test_helpers import (
    FakeAuthorVoiceRepository,
    FakeComposer,
    _resolved_model,
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


class TestAnalyzeErrorPaths:
    """analyze() raises the documented errors on missing dependencies."""

    @pytest.mark.asyncio
    async def test_raises_not_found_when_novel_missing(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[attr-defined]

        with pytest.raises(NotFoundError):
            await consume(service.analyze(uuid.uuid4(), None, uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_resolver_configuration_error_propagates_un_swallowed(
        self,
        composer: FakeComposer,
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
        service = make_service(
            composer,
            config,
            model_resolution=_RaisingResolution(),
        )
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]

        with pytest.raises(ConfigurationError):
            await consume(service.analyze(novel.id, None, uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_raises_configuration_error_when_no_composer(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """No PromptComposer → ConfigurationError (config is set so it's the
        next guard that fires)."""
        novel = make_novel()
        # Build the service with resolution set but composer=None — the
        # composer guard is the one that should fire.
        from unittest.mock import AsyncMock

        from narrare.analysis.author_voice_service import AuthorVoiceService
        from tests.unit.api.analysis._author_voice_test_helpers import (
            FakeAuthorVoiceRepository,
            FakeModelRegistry,
        )

        service = AuthorVoiceService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            chapter_repo=AsyncMock(),  # type: ignore[arg-type]
            repository=FakeAuthorVoiceRepository(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_resolution=StaticModelResolution(_resolved_model(config)),
            composer=None,
        )
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]

        with pytest.raises(ConfigurationError):
            await consume(service.analyze(novel.id, None, uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_agent_failure_propagates(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """An agent exception propagates (RULE-11 — never silently swallowed)."""
        novel = make_novel()
        chapters = [make_chapter(novel_id=novel.id) for _ in range(3)]

        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]
        service._chapter_repo.list_by_novel = AsyncMock(return_value=chapters)  # type: ignore[attr-defined]

        with (
            patch_mode1() as (MockAgent, _MockDeps, _mc),
            pytest.raises(RuntimeError, match="agent boom"),
        ):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(side_effect=RuntimeError("agent boom"))
            MockAgent.return_value = mock_agent

            await consume(service.analyze(novel.id, None, uuid.uuid4()))


class TestGetProfileAccessControl:
    """get_profile() enforces novel access control."""

    @pytest.mark.asyncio
    async def test_get_profile_raises_when_novel_missing(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[attr-defined]

        with pytest.raises(NotFoundError):
            await service.get_profile(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_get_profile_loads_via_repository(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        repository = FakeAuthorVoiceRepository()
        # Seed a profile via the fake's store.
        from narrare_core.profiles.author_voice import AuthorVoiceProfile

        seeded = AuthorVoiceProfile()
        await repository.save(novel.id, seeded)

        service = make_service(composer, config, repository=repository)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]

        result = await service.get_profile(novel.id, uuid.uuid4())
        assert result is seeded
        assert repository.load_calls == [novel.id]


class TestClearProfileAccessControl:
    """clear_profile() enforces novel access control + delegates to repository."""

    @pytest.mark.asyncio
    async def test_clear_profile_raises_when_novel_missing(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[attr-defined]

        with pytest.raises(NotFoundError):
            await service.clear_profile(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_clear_profile_delegates_to_repository(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        repository = FakeAuthorVoiceRepository()

        service = make_service(composer, config, repository=repository)
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]

        await service.clear_profile(novel.id, uuid.uuid4())
        assert repository.clear_calls == [novel.id]
