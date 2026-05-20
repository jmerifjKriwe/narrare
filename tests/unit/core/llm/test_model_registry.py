"""Tests for ModelRegistry (gateway.py).

Covers:
- ``ModelRegistry.get_model()`` — provider resolution, credential pass-through
- ``ModelRegistry.run()`` — convenience method for simple one-shot calls
- Edge cases: unknown provider, usage_limits parameter (Phase 1 preparation)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

# narrare: allow-agent reason="ModelRegistry tests use TestModel instead of real LLM"
from pydantic_ai.models.test import (
    TestModel,
)
from pydantic_ai.usage import UsageLimits

if TYPE_CHECKING:
    from narrare_core.llm.gateway import ModelRegistry

from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig


class TestModelRegistryGetModel:
    """Tests for ``ModelRegistry.get_model()``."""

    async def test_returns_model_for_known_provider(
        self,
        registry: ModelRegistry,
    ) -> None:
        """A known provider returns a configured Model instance."""
        config = ResolvedModelConfig(provider_name="test-provider", model_id="test-model")

        with patch("narrare_core.llm.gateway.get_provider") as mock_get:
            mock_get.return_value = lambda model_id, **kwargs: TestModel()
            model = await registry.get_model(config)

        assert isinstance(model, TestModel)

    async def test_raises_key_error_for_unknown_provider(
        self,
        registry: ModelRegistry,
    ) -> None:
        """An unregistered provider name raises KeyError."""
        config = ResolvedModelConfig(provider_name="does-not-exist", model_id="test")

        with pytest.raises(KeyError, match="does-not-exist"):
            await registry.get_model(config)

    async def test_passes_api_key_and_base_url_to_factory(
        self,
        registry: ModelRegistry,
    ) -> None:
        """Credentials (api_key, base_url) are forwarded to the provider factory."""
        captured: dict[str, object] = {}

        def capture_factory(model_id: str, **kwargs: object) -> TestModel:
            captured.update(kwargs)
            return TestModel()

        config = ResolvedModelConfig(provider_name="openrouter", model_id="gpt-4o")

        with patch("narrare_core.llm.gateway.get_provider") as mock_get:
            mock_get.return_value = capture_factory
            await registry.get_model(
                config,
                api_key="sk-or-test-key",
                base_url="https://openrouter.ai/api/v1",
            )

        assert captured.get("api_key") == "sk-or-test-key"
        assert captured.get("base_url") == "https://openrouter.ai/api/v1"

    async def test_passes_no_credentials_by_default(
        self,
        registry: ModelRegistry,
    ) -> None:
        """When no credentials are provided, factory receives None."""
        captured: dict[str, object] = {}

        def capture_factory(model_id: str, **kwargs: object) -> TestModel:
            captured.update(kwargs)
            return TestModel()

        config = ResolvedModelConfig(provider_name="openai", model_id="gpt-4o")

        with patch("narrare_core.llm.gateway.get_provider") as mock_get:
            mock_get.return_value = capture_factory
            await registry.get_model(config)

        # Factories receive None when no explicit credentials are given
        assert captured.get("api_key") is None
        assert captured.get("base_url") is None

    async def test_accepts_usage_limits_parameter_ignored_in_phase_0(
        self,
        registry: ModelRegistry,
    ) -> None:
        """``usage_limits`` is accepted but ignored in Phase 0.2.

        This parameter is prepared for Phase 1 of ADR-015.
        """
        config = ResolvedModelConfig(provider_name="test-p", model_id="test-m")

        with patch("narrare_core.llm.gateway.get_provider") as mock_get:
            mock_get.return_value = lambda model_id, **kwargs: TestModel()

            # Passing usage_limits=None should not cause errors
            model = await registry.get_model(config, usage_limits=None)

        assert isinstance(model, TestModel)

    async def test_passes_provider_name_and_model_id_correctly(
        self,
        registry: ModelRegistry,
    ) -> None:
        """The factory receives the correct model_id from config."""
        captured_model_ids: list[str] = []

        def capture_model_ids(model_id: str, **kwargs: object) -> TestModel:
            captured_model_ids.append(model_id)
            return TestModel()

        config = ResolvedModelConfig(
            provider_name="zai",
            model_id="glm-z1-32b",
        )

        with patch("narrare_core.llm.gateway.get_provider") as mock_get:
            mock_get.return_value = capture_model_ids
            await registry.get_model(config)

        assert captured_model_ids == ["glm-z1-32b"]


class TestModelRegistryRun:
    """Tests for ``ModelRegistry.run()`` convenience method."""

    async def test_returns_string_output_by_default(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """run() returns a string when output_type is not specified."""
        result = await registry_with_test_model.run(
            intent=LLMIntent.WRITE,
            prompt="Write something creative.",
            config=write_config,
            system_prompt="You are a novelist.",
        )

        assert isinstance(result, str)
        assert result == "Test response from pydantic-ai TestModel."

    async def test_run_passes_deps_to_agent(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """run() accepts and forwards deps to the Agent."""
        result = await registry_with_test_model.run(
            intent=LLMIntent.WRITE,
            prompt="Write something.",
            config=write_config,
            deps=None,
        )

        assert isinstance(result, str)

    async def test_accepts_system_prompt(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """system_prompt is passed through to the Agent."""
        result = await registry_with_test_model.run(
            intent=LLMIntent.GENERATE,
            prompt="Generate a name for a fantasy city.",
            config=write_config,
            system_prompt="You are a fantasy world-building assistant.",
        )

        assert isinstance(result, str)
        assert result  # non-empty

    async def test_accepts_usage_limits(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """usage_limits parameter is accepted but ignored in Phase 0.2."""
        result = await registry_with_test_model.run(
            intent=LLMIntent.NAME_GENERATE,
            prompt="Suggest a character name.",
            config=write_config,
            usage_limits=None,
        )

        assert isinstance(result, str)
        assert result == "Test response from pydantic-ai TestModel."

    async def test_run_without_system_prompt(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """run() works with system_prompt=None (defaults to empty string)."""
        result = await registry_with_test_model.run(
            intent=LLMIntent.CHAT,
            prompt="Hello!",
            config=write_config,
        )

        assert isinstance(result, str)
        assert result == "Test response from pydantic-ai TestModel."


class TestModelRegistryEdgeCases:
    """Edge cases for ModelRegistry."""

    async def test_get_model_config_without_streams(
        self,
        registry: ModelRegistry,
    ) -> None:
        """ResolvedModelConfig defaults work (streams=False, temperature=0.7)."""
        config = ResolvedModelConfig(provider_name="test-p", model_id="test-m")

        with patch("narrare_core.llm.gateway.get_provider") as mock_get:
            mock_get.return_value = lambda model_id, **kwargs: TestModel()
            model = await registry.get_model(config)

        assert isinstance(model, TestModel)

    async def test_run_empty_prompt(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """run() handles an empty prompt string."""
        result = await registry_with_test_model.run(
            intent=LLMIntent.CHAT,
            prompt="",
            config=write_config,
        )

        assert isinstance(result, str)


class TestModelRegistryUsageLimits:
    """UsageLimits werden korrekt an agent.run() übergeben."""

    async def test_run_passes_usage_limits_to_agent(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """usage_limits-Parameter erreicht agent.run()."""
        limits = UsageLimits(request_limit=5, total_tokens_limit=1000)

        result = await registry_with_test_model.run(
            intent=LLMIntent.WRITE,
            prompt="Hello",
            config=write_config,
            usage_limits=limits,
        )

        assert result is not None
        assert isinstance(result, str)
