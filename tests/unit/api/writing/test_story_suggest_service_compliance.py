"""RULE-11 error-handling tests for StorySuggestService (ADR-054 D8).

Verifies that errors propagate (RULE-11) instead of being silently swallowed:

- Invocation-composition failures propagate (D8).
- Missing novel raises NotFoundError.
- Missing composer raises ConfigurationError (defensive guard).
- Missing model config raises NotFoundError.

Behavioural Mode 1 + SSE tests live in ``test_story_suggest_service.py``
(RULE-04 split).

See:
    ADR-054 — Inline Feature-Prompt Debt Migration (D8)
    CONSTRAINTS.md RULE-11
    WRITE-009 — Writer's Unblock Tools
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from narrare_core.llm.model_config import ResolvedModelConfig
from tests.unit.api.writing._story_suggest_test_helpers import (
    FakeComposer,
    FakeModelRegistry,
    make_novel,
    make_request,
    make_service,
)

if TYPE_CHECKING:
    from narrare.writing.schemas_story_suggest import StorySuggestRequest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(provider_name="test", model_id="test-model")


@pytest.fixture
def request_body() -> StorySuggestRequest:
    return make_request()


# ---------------------------------------------------------------------------
# RULE-11 (ADR-054 D8): errors propagate, not swallowed
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """RULE-11: errors must propagate, not be silently swallowed."""

    @pytest.mark.asyncio
    async def test_compose_invocation_failure_propagates(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: StorySuggestRequest,
    ) -> None:
        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with (
            patch("narrare_core.agents.story_suggest_agent.StorySuggestAgent"),
            patch("narrare_core.agents.story_suggest_types.StorySuggestDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(side_effect=RuntimeError("pipeline offline")),
            ),
            pytest.raises(RuntimeError, match="pipeline offline"),
        ):
            async for _ in service.suggest(uuid.uuid4(), uuid.uuid4(), request_body):  # type: ignore[arg-type]
                pass

    @pytest.mark.asyncio
    async def test_missing_novel_raises_not_found_error(
        self,
        composer: FakeComposer,
        config: ResolvedModelConfig,
        request_body: StorySuggestRequest,
    ) -> None:
        from narrare_core.shared.errors import NotFoundError

        service = make_service(composer, config)
        service._novel_repo.get_by_id.return_value = None  # type: ignore[attr-defined]

        with pytest.raises(NotFoundError, match="Novel"):
            async for _ in service.suggest(uuid.uuid4(), uuid.uuid4(), request_body):  # type: ignore[arg-type]
                pass

    @pytest.mark.asyncio
    async def test_missing_composer_raises_configuration_error(
        self,
        config: ResolvedModelConfig,
        request_body: StorySuggestRequest,
    ) -> None:
        from narrare.writing.story_suggest_service import StorySuggestService
        from narrare_core.shared.errors import ConfigurationError

        service = StorySuggestService(
            novel_repo=AsyncMock(),  # type: ignore[arg-type]
            model_registry=FakeModelRegistry(),  # type: ignore[arg-type]
            model_config=config,
            composer=None,
        )
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]

        with pytest.raises(ConfigurationError, match="PromptComposer"):
            async for _ in service.suggest(uuid.uuid4(), uuid.uuid4(), request_body):  # type: ignore[arg-type]
                pass

    @pytest.mark.asyncio
    async def test_missing_model_config_raises_not_found_error(
        self,
        composer: FakeComposer,
        request_body: StorySuggestRequest,
    ) -> None:
        from narrare_core.shared.errors import NotFoundError

        service = make_service(composer, config=None)  # type: ignore[arg-type]
        service._novel_repo.get_by_id.return_value = make_novel()  # type: ignore[attr-defined]
        # Override registry to a fake (make_service already sets one, but
        # model_config=None is the trigger here).
        service._registry = FakeModelRegistry()  # type: ignore[assignment]

        with pytest.raises(NotFoundError, match="Model config"):
            async for _ in service.suggest(uuid.uuid4(), uuid.uuid4(), request_body):  # type: ignore[arg-type]
                pass
