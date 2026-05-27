"""Regression test: Settings routers must not hardcode model names or providers.

Settings routers resolve model configurations through user settings and
service protocols. Hardcoded model names would bypass user configuration.
"""

from __future__ import annotations

import inspect


def _get_source(func_path: str) -> str:
    import importlib

    module_path, func_name = func_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    func = getattr(module, func_name)
    return inspect.getsource(func)


class TestSettingsRouterNoHardcodedModels:
    """Settings DI functions must not hardcode specific model IDs."""

    def test_providers_service_no_hardcoded_anthropic(self) -> None:
        source = _get_source("narrare.settings.router_ai_providers._get_providers_service")
        assert '"anthropic"' not in source, "_get_providers_service hardcodes 'anthropic'"

    def test_providers_service_no_hardcoded_model(self) -> None:
        source = _get_source("narrare.settings.router_ai_providers._get_providers_service")
        assert '"gpt-' not in source
        assert '"claude' not in source

    def test_ai_settings_service_no_hardcoded_model(self) -> None:
        source = _get_source("narrare.settings.router_ai._get_ai_settings_service")
        assert '"gpt-' not in source
        assert '"claude' not in source

    def test_provider_models_service_no_hardcoded_model(self) -> None:
        source = _get_source("narrare.settings.router_ai._get_provider_models_service")
        assert '"gpt-' not in source
        assert '"claude' not in source


class TestSettingsRouterNoHardcodedProviderDefaults:
    """Settings routers should not hardcode default provider names."""

    def test_main_router_no_hardcoded_providers(self) -> None:
        import narrare.settings.router as settings_router

        source = inspect.getsource(settings_router)
        assert '"anthropic"' not in source, "settings/router.py hardcodes 'anthropic'"
        assert '"openai"' not in source, "settings/router.py hardcodes 'openai'"

    def test_tones_router_no_hardcoded_models(self) -> None:
        import narrare.settings.router_tones as tones_router

        source = inspect.getsource(tones_router)
        assert '"anthropic"' not in source
        assert '"gpt-' not in source


class TestSettingsRouterUsesServiceProtocols:
    """Settings routers should use config/settings, not hardcoded values."""

    def test_providers_service_uses_config(self) -> None:
        """_get_providers_service should use settings repository, not hardcodings."""
        source = _get_source("narrare.settings.router_ai_providers._get_providers_service")
        # Should reference UserProvidersRepository or UserProvidersService
        assert "UserProvidersRepository" in source or "UserProvidersService" in source, (
            "_get_providers_service should use repository or service class"
        )
