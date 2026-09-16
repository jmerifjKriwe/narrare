"""Regression test: Planning router must not hardcode model names or providers.

The planning feature resolves provider configurations through user settings.
Hardcoded model names would bypass user-visible provider selection UI.
"""

from __future__ import annotations

import inspect


class TestPlanningRouterNoHardcodedModels:
    """Planning DI function must not hardcode specific model IDs."""

    def test_get_service_no_hardcoded_anthropic(self) -> None:
        from narrare.planning._service_factory import get_storyboard_service

        source = inspect.getsource(get_storyboard_service)
        assert '"anthropic"' not in source, "planning service factory hardcodes 'anthropic'"

    def test_get_service_no_hardcoded_model(self) -> None:
        from narrare.planning._service_factory import get_storyboard_service

        source = inspect.getsource(get_storyboard_service)
        assert '"gpt-' not in source
        assert '"claude' not in source

    def test_get_service_no_hardcoded_provider_specific(self) -> None:
        from narrare.planning._service_factory import get_storyboard_service

        source = inspect.getsource(get_storyboard_service)
        assert '"openai"' not in source, "planning service factory hardcodes 'openai'"


class TestPlanningRouterUsesSettings:
    """Planning DI should resolve models via settings, not hardcoded values."""

    def test_get_service_uses_user_settings(self) -> None:
        """Service factory should resolve provider/model from user settings.

        Migrated for ADR-086 L21: the factory wires the settings-driven
        model-routing resolver behind a ``LazyModelResolution`` instead of
        resolving at construction — the routing source is unchanged
        (RULE-18), only the timing moved. The no-hardcode pins above keep
        guarding against literal model/provider strings.
        """
        from narrare.planning._service_factory import get_storyboard_service

        source = inspect.getsource(get_storyboard_service)
        # Should route through the resolver / lazy resolution, not hardcode
        assert "resolver" in source.lower() or "resolution" in source.lower(), (
            "service factory should resolve from the routing cascade, not hardcode"
        )

    def test_get_service_uses_llm_gateway(self) -> None:
        """Service factory should delegate LLM calls through the gateway."""
        from narrare.planning._service_factory import get_storyboard_service

        source = inspect.getsource(get_storyboard_service)
        # Should reference LLMGateway or gateway
        assert "gateway" in source.lower() or "LLM" in source, (
            "service factory should use LLM gateway"
        )
