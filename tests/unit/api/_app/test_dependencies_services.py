"""Unit tests for ``narrare._app.dependencies_services`` — DI factories.

Tests the service-layer dependency factory functions:
- ``build_system_default_config`` — system default model config
- ``get_graph_state_store`` — graph state store factory
- ``get_template_repository`` / ``get_template_api_service`` / ``get_cascade_resolver``
- ``get_user_providers_service`` / ``get_user_ai_settings_service``
  / ``get_project_ai_settings_service``
- ``get_model_routing_resolver``
- ``ModelResolution`` / ``LazyModelResolution`` / ``StaticModelResolution``
  — lazy model resolution primitives
"""

from __future__ import annotations

from typing import Any

import pytest

from narrare._app.dependencies_services import (
    LazyModelResolution,
    ModelResolution,
    StaticModelResolution,
    SystemModelCategory,
    build_system_default_config,
    get_cascade_resolver,
    get_graph_state_store,
    get_model_routing_resolver,
    get_project_ai_settings_service,
    get_template_api_service,
    get_template_repository,
    get_user_ai_settings_service,
    get_user_providers_service,
)
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel

# ---------------------------------------------------------------------------
# Fake session
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal async session for repository constructors."""


# ---------------------------------------------------------------------------
# build_system_default_config
# ---------------------------------------------------------------------------


class TestBuildSystemDefaultConfig:
    def test_writing_category_returns_writing_model(self) -> None:
        config = build_system_default_config(category=SystemModelCategory.WRITING)
        assert config.provider_name != ""
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_analysis_category_returns_analysis_model(self) -> None:
        config = build_system_default_config(category=SystemModelCategory.ANALYSIS)
        assert config.provider_name != ""
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_custom_temperature_and_max_tokens(self) -> None:
        config = build_system_default_config(
            category=SystemModelCategory.WRITING,
            temperature=0.3,
            max_tokens=1024,
        )
        assert config.temperature == 0.3
        assert config.max_tokens == 1024


# ---------------------------------------------------------------------------
# Factory functions (verify correct types are returned)
# ---------------------------------------------------------------------------


class TestFactoryFunctions:
    def test_get_graph_state_store(self) -> None:
        session: Any = _FakeSession()
        store = get_graph_state_store(session)  # type: ignore[arg-type]
        assert store.__class__.__name__ == "PostgresGraphStateStore"

    def test_get_template_repository(self) -> None:
        session: Any = _FakeSession()
        repo = get_template_repository(session)  # type: ignore[arg-type]
        assert repo.__class__.__name__ == "TemplateRepository"

    def test_get_template_api_service(self) -> None:
        session: Any = _FakeSession()
        service = get_template_api_service(session)  # type: ignore[arg-type]
        assert service.__class__.__name__ == "TemplateApiService"

    def test_get_cascade_resolver(self) -> None:
        session: Any = _FakeSession()
        resolver = get_cascade_resolver(session)  # type: ignore[arg-type]
        assert resolver.__class__.__name__ == "CascadeResolver"

    def test_get_user_providers_service(self) -> None:
        session: Any = _FakeSession()
        service = get_user_providers_service(session)  # type: ignore[arg-type]
        assert service.__class__.__name__ == "UserProvidersService"

    def test_get_user_ai_settings_service(self) -> None:
        session: Any = _FakeSession()
        service = get_user_ai_settings_service(session)  # type: ignore[arg-type]
        assert service.__class__.__name__ == "UserAiSettingsService"

    def test_get_project_ai_settings_service(self) -> None:
        session: Any = _FakeSession()
        service = get_project_ai_settings_service(session)  # type: ignore[arg-type]
        assert service.__class__.__name__ == "ProjectAiSettingsService"

    def test_get_model_routing_resolver(self) -> None:
        session: Any = _FakeSession()
        resolver = get_model_routing_resolver(session)  # type: ignore[arg-type]
        assert resolver.__class__.__name__ == "ModelRoutingResolverImpl"


# ---------------------------------------------------------------------------
# Model resolution primitives (lazy/static)
# ---------------------------------------------------------------------------

_PROBE_MODEL = ResolvedModel(
    config=ResolvedModelConfig(provider_name="anthropic", model_id="claude-haiku"),
    source="probe",
)


class _CountingFactory:
    """Async factory that counts invocations and can fail N times first."""

    def __init__(self, failures: int = 0) -> None:
        self._failures = failures
        self.calls = 0

    async def __call__(self) -> ResolvedModel:
        self.calls += 1
        if self.calls <= self._failures:
            msg = "simulated resolution failure"
            raise RuntimeError(msg)
        return _PROBE_MODEL


class TestLazyModelResolution:
    async def test_resolve_invokes_factory_once_and_caches(self) -> None:
        factory = _CountingFactory()
        resolution = LazyModelResolution(factory)

        first = await resolution.resolve()
        second = await resolution.resolve()

        assert factory.calls == 1
        assert first is second
        assert first is _PROBE_MODEL

    async def test_resolve_error_not_cached_retries_factory(self) -> None:
        factory = _CountingFactory(failures=1)
        resolution = LazyModelResolution(factory)

        with pytest.raises(RuntimeError, match="simulated resolution failure"):
            await resolution.resolve()

        resolved = await resolution.resolve()

        assert factory.calls == 2
        assert resolved is _PROBE_MODEL

    async def test_resolve_after_error_then_caches_success(self) -> None:
        factory = _CountingFactory(failures=1)
        resolution = LazyModelResolution(factory)

        with pytest.raises(RuntimeError, match="simulated resolution failure"):
            await resolution.resolve()
        resolved = await resolution.resolve()
        cached = await resolution.resolve()

        assert factory.calls == 2
        assert resolved is cached
        assert cached is _PROBE_MODEL


class TestStaticModelResolution:
    async def test_resolve_returns_fixed_model(self) -> None:
        resolution = StaticModelResolution(_PROBE_MODEL)

        resolved = await resolution.resolve()

        assert resolved is _PROBE_MODEL

    async def test_resolve_is_idempotent(self) -> None:
        resolution = StaticModelResolution(_PROBE_MODEL)

        first = await resolution.resolve()
        second = await resolution.resolve()

        assert first is second


class TestModelResolutionContracts:
    async def test_lazy_satisfies_protocol(self) -> None:
        resolution: ModelResolution = LazyModelResolution(_CountingFactory())

        assert isinstance(resolution, ModelResolution)
        assert isinstance(await resolution.resolve(), ResolvedModel)

    async def test_static_satisfies_protocol(self) -> None:
        resolution: ModelResolution = StaticModelResolution(_PROBE_MODEL)

        assert isinstance(resolution, ModelResolution)
        assert isinstance(await resolution.resolve(), ResolvedModel)
