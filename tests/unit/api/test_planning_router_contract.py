"""Regression test: Planning router must not hardcode model names or providers.

The planning feature resolves provider configurations through user settings.
Hardcoded model names would bypass user-visible provider selection UI.
"""

from __future__ import annotations

import inspect


class TestPlanningRouterNoHardcodedModels:
    """Planning DI function must not hardcode specific model IDs."""

    def test_get_service_no_hardcoded_anthropic(self) -> None:
        import narrare.planning.router as planning_router

        source = inspect.getsource(planning_router._get_service)
        assert '"anthropic"' not in source, "planning _get_service hardcodes 'anthropic'"

    def test_get_service_no_hardcoded_model(self) -> None:
        import narrare.planning.router as planning_router

        source = inspect.getsource(planning_router._get_service)
        assert '"gpt-' not in source
        assert '"claude' not in source

    def test_get_service_no_hardcoded_provider_specific(self) -> None:
        import narrare.planning.router as planning_router

        source = inspect.getsource(planning_router._get_service)
        assert '"openai"' not in source, "planning _get_service hardcodes 'openai'"


class TestPlanningRouterUsesSettings:
    """Planning DI should resolve models via settings, not hardcoded values."""

    def test_get_service_uses_user_settings(self) -> None:
        """_get_service should resolve provider/model from user settings."""
        import narrare.planning.router as planning_router

        source = inspect.getsource(planning_router._get_service)
        # Should reference user settings or planning config, not hardcoded strings
        assert "settings" in source.lower() or "config" in source.lower(), (
            "_get_service should resolve from settings/config, not hardcode"
        )

    def test_get_service_uses_llm_gateway(self) -> None:
        """_get_service should delegate LLM calls through the gateway."""
        import narrare.planning.router as planning_router

        source = inspect.getsource(planning_router._get_service)
        # Should reference LLMGateway or gateway
        assert "gateway" in source.lower() or "LLM" in source, "_get_service should use LLM gateway"
