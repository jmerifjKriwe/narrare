"""Error-handling / RULE-11 tests for CoreferenceService (ANAL-005).

Split from ``test_coreference_service.py`` for RULE-04 compliance
(< 300 lines). Verifies that errors propagate — the service never
silently swallows them (RULE-11).

See:
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-11 (no silent failures).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.analysis._coreference_test_helpers import (
    FakeComposer,
    consume,
    make_chapter,
    make_novel,
    make_service,
    patch_mode1,
)


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


class TestErrorHandling:
    """Errors propagate — the service never swallows them (RULE-11)."""

    @pytest.mark.asyncio
    async def test_chapter_not_found_raises_not_found_error(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare_core.shared.errors import NotFoundError

        service = make_service(composer, config)
        service._chapter_repo.get.return_value = None  # type: ignore[attr-defined]

        with pytest.raises(NotFoundError):
            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_novel_not_found_raises_not_found_error(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare_core.shared.errors import NotFoundError

        service = make_service(composer, config)
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = None  # type: ignore[attr-defined]

        with pytest.raises(NotFoundError):
            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_no_composer_raises_configuration_error(
        self,
        config: ResolvedModelConfig,
    ) -> None:
        from narrare_core.shared.errors import ConfigurationError

        service = make_service(FakeComposer(), config)
        service._composer = None  # type: ignore[assignment]
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with pytest.raises(ConfigurationError):
            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_no_model_config_raises_not_found_error(
        self,
        composer: FakeComposer,
    ) -> None:
        from narrare_core.shared.errors import NotFoundError

        service = make_service(composer, ResolvedModelConfig(provider_name="t", model_id="t"))
        service._config = None  # type: ignore[assignment]
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with pytest.raises(NotFoundError):
            await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_agent_failure_propagates(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
    ) -> None:
        """RULE-11: an agent failure must propagate, not be swallowed."""
        service = make_service(composer, config)
        service._chapter_repo.get.return_value = make_chapter()  # type: ignore[attr-defined]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with patch_mode1() as (MockAgent, _MockDeps, _mc):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM blew up"))
            MockAgent.return_value = mock_agent

            with pytest.raises(RuntimeError, match="LLM blew up"):
                await consume(service.analyze(uuid.uuid4(), uuid.uuid4()))  # type: ignore[arg-type]
