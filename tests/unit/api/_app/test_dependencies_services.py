"""Unit tests for ``narrare._app.dependencies_services`` — DI factories.

Tests the service-layer dependency factory functions:
- ``build_system_default_config`` — system default model config
- ``get_graph_state_store`` — graph state store factory
- ``get_template_repository`` / ``get_template_api_service`` / ``get_cascade_resolver``
- ``get_user_providers_service`` / ``get_user_ai_settings_service``
  / ``get_project_ai_settings_service``
- ``get_model_routing_resolver``
"""

from __future__ import annotations

from typing import Any

from narrare._app.dependencies_services import (
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
