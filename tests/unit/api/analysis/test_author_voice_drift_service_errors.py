"""RULE-11 error-path tests for AuthorVoiceDriftService (ANAL-009 Phase 2B / ADR-074).

Split from ``test_author_voice_drift_service.py`` for RULE-04 compliance
(test file < 300 lines). Covers the failure modes the happy-path file does not:

- Novel not found / inaccessible -> NotFoundError.
- Unconfigured provider (routing cascade) -> ConfigurationError propagates
  un-swallowed from the entry point (ADR-086 lazy resolution).
- No PromptComposer -> ConfigurationError.

Mirrors ``test_author_voice_service_errors.py`` (ADR-055 / ADR-074 precedent).

See:
    ADR-074 — Author Voice Storage Contract.
    CONSTRAINTS.md RULE-11 (no silent failures).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare.analysis.author_voice_drift_service import AuthorVoiceDriftService
from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.shared.errors import ConfigurationError, NotFoundError
from tests.unit.api.analysis._author_voice_drift_test_helpers import (
    FakeAuthorVoiceRepository,
    FakeModelRegistry,
    _resolved_model,
    consume,
    make_novel,
    make_service,
)

if TYPE_CHECKING:
    from narrare_core.llm.model_routing import ResolvedModel


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


class TestAuthorVoiceDriftErrors:
    """Missing novel / unconfigured provider / composer raise typed errors (RULE-11)."""

    @pytest.mark.asyncio
    async def test_missing_novel_raises_not_found(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        novel = make_novel()
        service = make_service(novel=None, chapters=[], profile=None, config=config)

        with pytest.raises(NotFoundError):
            await consume(service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest()))

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
        service = make_service(
            novel=novel,
            chapters=[],
            profile=None,
            config=config,
            model_resolution=_RaisingResolution(),
        )

        with pytest.raises(ConfigurationError):
            await consume(service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest()))

    @pytest.mark.asyncio
    async def test_missing_composer_raises_configuration_error(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        """No PromptComposer → ConfigurationError (resolution is set so it's
        the next guard that fires)."""
        from unittest.mock import AsyncMock

        novel = make_novel()
        service = AuthorVoiceDriftService(
            novel_repo=AsyncMock(),
            chapter_repo=AsyncMock(),
            author_voice_repo=FakeAuthorVoiceRepository(),
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_resolution=StaticModelResolution(_resolved_model(config)),
            composer=None,
        )
        service._novel_repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[attr-defined]

        with pytest.raises(ConfigurationError):
            await consume(service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest()))
