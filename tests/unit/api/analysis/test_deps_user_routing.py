"""User-routing migration tests for analysis dependency factories (Tasks 2a/2b).

Regression-first proof that the analysis factories (readability, pov) resolve
the model via the per-user ``ModelRoutingResolver`` cascade (instead of the
legacy ``build_system_default_config``) with the correct intent + user_id +
novel_id, and that the resolved config + api_key/base_url reach the services.

Split for the RULE-04 test-file hard limit:
- ``test_deps_user_routing.py`` (this file) — structural + readability/pov.
- ``test_deps_user_routing_factories.py`` — split-factory execution
  (beta_reader/character_voice/coreference + the Task 2b voice factories).
- ``test_deps_user_routing_credentials.py`` — credentials reach the actual
  ``ModelRegistry.get_model`` resolution point inside the services/runners.

Sentiment is intentionally unmigrated: it is purely deterministic (ADR-021)
with no LLM call — pinned by a guard test.

Pattern reference: ``tests/unit/api/kb/test_deps_user_routing.py`` (Task 1a).
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return (wizard provider)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


def _fake_resolver() -> tuple[MagicMock, ResolvedModel]:
    """A spec'd fake resolver whose resolve() returns the user's model."""
    resolved = ResolvedModel(
        config=_user_config(),
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
    )
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(return_value=resolved)
    return resolver, resolved


# ===========================================================================
# Structural — factories are async, user-scoped, legacy-pattern-free
# ===========================================================================


class TestFactoryStructure:
    """Structural regressions: signature gains user routing, legacy is gone."""

    def test_get_readability_service_is_async_with_user_routing_params(self) -> None:
        from narrare.analysis.dependencies import get_readability_service

        assert inspect.iscoroutinefunction(get_readability_service)
        params = list(inspect.signature(get_readability_service).parameters)
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    def test_get_pov_service_is_async_with_user_routing_params(self) -> None:
        from narrare.analysis.dependencies import get_pov_service

        assert inspect.iscoroutinefunction(get_pov_service)
        params = list(inspect.signature(get_pov_service).parameters)
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    def test_get_beta_reader_service_resolves_via_resolver(self) -> None:
        import narrare.analysis.dependencies_beta_reader as mod

        assert inspect.iscoroutinefunction(mod.get_beta_reader_service)
        params = list(inspect.signature(mod.get_beta_reader_service).parameters)
        assert "user_id" in params
        assert "novel_id" in params

    def test_get_character_voice_service_is_async_with_user_routing_params(self) -> None:
        from narrare.analysis.dependencies_character_voice import (
            get_character_voice_service,
        )

        assert inspect.iscoroutinefunction(get_character_voice_service)
        params = list(inspect.signature(get_character_voice_service).parameters)
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    def test_get_coreference_service_is_async_without_novel_id(self) -> None:
        """Coreference router is chapter-scoped (no novel_id) — user routing only."""
        from narrare.analysis.dependencies_coreference import get_coreference_service

        assert inspect.iscoroutinefunction(get_coreference_service)
        params = list(inspect.signature(get_coreference_service).parameters)
        assert "user_id" in params
        assert "session" in params
        assert "novel_id" not in params

    def test_get_voice_check_service_is_async_without_novel_id(self) -> None:
        """Voice-check router is chapter-scoped (no novel_id) — user routing only."""
        from narrare.analysis.dependencies_voice_check import get_voice_check_service

        assert inspect.iscoroutinefunction(get_voice_check_service)
        params = list(inspect.signature(get_voice_check_service).parameters)
        assert "user_id" in params
        assert "session" in params
        assert "novel_id" not in params

    def test_get_voice_drift_service_is_async_with_user_routing_params(self) -> None:
        from narrare.analysis.dependencies_voice_drift import get_voice_drift_service

        assert inspect.iscoroutinefunction(get_voice_drift_service)
        params = list(inspect.signature(get_voice_drift_service).parameters)
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    def test_get_author_voice_service_is_async_with_user_routing_params(self) -> None:
        from narrare.analysis.dependencies_author_voice import get_author_voice_service

        assert inspect.iscoroutinefunction(get_author_voice_service)
        params = list(inspect.signature(get_author_voice_service).parameters)
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    def test_get_author_voice_drift_service_is_async_with_user_routing_params(self) -> None:
        from narrare.analysis.dependencies_author_voice_drift import (
            get_author_voice_drift_service,
        )

        assert inspect.iscoroutinefunction(get_author_voice_drift_service)
        params = list(inspect.signature(get_author_voice_drift_service).parameters)
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    @pytest.mark.parametrize(
        ("module_name", "attribute"),
        [
            ("narrare.analysis.dependencies", "get_readability_service"),
            ("narrare.analysis.dependencies", "get_pov_service"),
        ],
    )
    def test_factories_do_not_use_system_default_config(
        self, module_name: str, attribute: str
    ) -> None:
        import importlib

        mod = importlib.import_module(module_name)
        source = inspect.getsource(mod)
        assert "build_system_default_config" not in source
        assert "SystemModelCategory" not in source

    @pytest.mark.parametrize(
        "module_name",
        [
            "narrare.analysis.dependencies_beta_reader",
            "narrare.analysis.dependencies_character_voice",
            "narrare.analysis.dependencies_coreference",
            "narrare.analysis.dependencies_voice_check",
            "narrare.analysis.dependencies_voice_drift",
            "narrare.analysis.dependencies_author_voice",
            "narrare.analysis.dependencies_author_voice_drift",
        ],
    )
    def test_split_factories_do_not_use_system_default_config(self, module_name: str) -> None:
        import importlib

        mod = importlib.import_module(module_name)
        source = inspect.getsource(mod)
        assert "build_system_default_config" not in source
        assert "SystemModelCategory" not in source

    def test_sentiment_factory_stays_deterministic(self) -> None:
        """Sentiment has no LLM call (ADR-021) — no model routing, no legacy config."""
        import importlib

        mod = importlib.import_module("narrare.analysis.dependencies")
        source = inspect.getsource(mod.get_sentiment_service)
        assert "build_system_default_config" not in source
        assert "get_model_routing_resolver" not in source
        assert "get_model_registry" not in source


# ===========================================================================
# Factory execution — resolver resolves with intent + user_id + novel_id
# ===========================================================================


class TestReadabilityFactoryUserRouting:
    """get_readability_service resolves via the cascade (ANALYSE + novel)."""

    async def test_resolves_analyse_for_user_and_novel(self) -> None:
        from narrare.analysis.dependencies import get_readability_service
        from narrare.analysis.services.readability_service import ReadabilityService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.analysis.dependencies.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare._app.dependencies.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare._app.dependencies.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare._app.dependencies.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ),
        ):
            service = await get_readability_service(
                novel_id=novel_id,
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.ANALYSE, UUID(user_id), novel_id)
        assert isinstance(service, ReadabilityService)
        assert service._model_config is resolved.config
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL


class TestPOVFactoryUserRouting:
    """get_pov_service resolves via the cascade (ANALYSE + novel)."""

    async def test_resolves_analyse_for_user_and_novel(self) -> None:
        from narrare.analysis.dependencies import get_pov_service
        from narrare.analysis.services.pov_service import POVService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.analysis.dependencies.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare._app.dependencies.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare._app.dependencies.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare._app.dependencies.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ),
        ):
            service = await get_pov_service(
                novel_id=novel_id,
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.ANALYSE, UUID(user_id), novel_id)
        assert isinstance(service, POVService)
        assert service._model_config is resolved.config
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL
