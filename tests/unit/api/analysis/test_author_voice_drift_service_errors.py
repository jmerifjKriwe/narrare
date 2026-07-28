"""RULE-11 error-path tests for AuthorVoiceDriftService (ANAL-009 Phase 2B / ADR-074).

Split from ``test_author_voice_drift_service.py`` for RULE-04 compliance
(test file < 300 lines). Covers the failure modes the happy-path file does not:

- Novel not found / inaccessible -> NotFoundError.
- No model config -> NotFoundError.
- No PromptComposer -> ConfigurationError.

Mirrors ``test_author_voice_service_errors.py`` (ADR-055 / ADR-074 precedent).

See:
    ADR-074 — Author Voice Storage Contract.
    CONSTRAINTS.md RULE-11 (no silent failures).
"""

from __future__ import annotations

import uuid

import pytest

from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._author_voice_drift_test_helpers import (
    consume,
    make_novel,
    make_service,
)


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


class TestAuthorVoiceDriftErrors:
    """Missing novel / config / composer raise typed errors (RULE-11)."""

    @pytest.mark.asyncio
    async def test_missing_novel_raises_not_found(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare_core.shared.errors import NotFoundError

        novel = make_novel()
        service = make_service(novel=None, chapters=[], profile=None, config=config)

        with pytest.raises(NotFoundError):
            await consume(service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest()))

    @pytest.mark.asyncio
    async def test_missing_model_config_raises_not_found(self) -> None:
        from narrare_core.shared.errors import NotFoundError

        novel = make_novel()
        service = make_service(
            novel=novel,
            chapters=[],
            profile=None,
            config=ResolvedModelConfig(provider_name="test", model_id="m"),
        )
        service._config = None  # type: ignore[reportPrivateUsage]

        with pytest.raises(NotFoundError):
            await consume(service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest()))

    @pytest.mark.asyncio
    async def test_missing_composer_raises_configuration_error(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare_core.shared.errors import ConfigurationError

        novel = make_novel()
        service = make_service(novel=novel, chapters=[], profile=None, config=config)
        service._composer = None  # type: ignore[reportPrivateUsage]

        with pytest.raises(ConfigurationError):
            await consume(service.run_stream(novel.id, uuid.uuid4(), AuthorVoiceDriftRequest()))
