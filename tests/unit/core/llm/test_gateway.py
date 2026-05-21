"""Tests for llm/gateway.py — ModelRegistry run() and stream() methods."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from narrare_core.llm.result import StreamChunk

from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig


class TestModelRegistryRun:
    async def test_returns_string_on_success(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """ModelRegistry.run() returns string output when Agent succeeds."""
        result = await registry_with_test_model.run(
            LLMIntent.WRITE,
            prompt="Write something.",
            config=write_config,
        )

        assert isinstance(result, str)
        assert result == "Test response from pydantic-ai TestModel."

    async def test_passes_system_prompt(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """ModelRegistry.run() passes system_prompt to Agent."""
        # With TestModel this doesn't error — just verify it doesn't raise
        result = await registry_with_test_model.run(
            LLMIntent.WRITE,
            prompt="Write.",
            config=write_config,
            system_prompt="You are a helpful writer.",
        )
        assert isinstance(result, str)

    async def test_passes_credentials_to_get_model(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """ModelRegistry.run() passes api_key and base_url to get_model."""
        captured_kwargs: list[dict[str, object]] = []

        original_get_model = registry_with_test_model.get_model

        async def capture_get_model(config, **kwargs):
            captured_kwargs.append(kwargs)
            return await original_get_model(config, **kwargs)

        with patch.object(
            registry_with_test_model,
            "get_model",
            side_effect=capture_get_model,
        ):
            await registry_with_test_model.run(
                LLMIntent.WRITE,
                prompt="Write.",
                config=write_config,
                api_key="sk-test-key",
                base_url="https://custom.api/v1",
            )

        assert captured_kwargs[0]["api_key"] == "sk-test-key"
        assert captured_kwargs[0]["base_url"] == "https://custom.api/v1"


class TestModelRegistryStream:
    """Tests for the streaming method."""

    async def test_stream_yields_text_chunks_and_final_chunk(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """ModelRegistry.stream() yields text chunks and a final chunk."""
        chunks: list[StreamChunk] = []
        async for chunk in registry_with_test_model.stream(
            intent=LLMIntent.WRITE,
            system_prompt="System.",
            user_prompt="Write.",
            config=write_config,
        ):
            chunks.append(chunk)

        # TestModel returns a single text response
        # Should have at least 1 text chunk + 1 final chunk
        assert len(chunks) >= 1
        final_chunks = [c for c in chunks if c.is_final]
        assert len(final_chunks) == 1
        assert final_chunks[0].text == ""
        assert final_chunks[0].usage is not None
        assert final_chunks[0].usage.total_tokens > 0

    async def test_stream_with_credentials(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """ModelRegistry.stream() passes credentials to get_model."""
        captured_kwargs: list[dict[str, object]] = []

        original_get_model = registry_with_test_model.get_model

        async def capture_get_model(config, **kwargs):
            captured_kwargs.append(kwargs)
            return await original_get_model(config, **kwargs)

        with patch.object(
            registry_with_test_model,
            "get_model",
            side_effect=capture_get_model,
        ):
            async for _ in registry_with_test_model.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=write_config,
                api_key="sk-or-test-key",
                base_url="https://openrouter.ai/api/v1",
            ):
                pass

        assert captured_kwargs[0]["api_key"] == "sk-or-test-key"
        assert captured_kwargs[0]["base_url"] == "https://openrouter.ai/api/v1"


class TestTokenLimitProfile:
    """Token-Limit-Profile → UsageLimits Mapping."""

    def test_profile_to_limits_returns_usage_limits(self) -> None:
        """Bekannte Profile geben UsageLimits zurück."""
        for profile in ("quick", "balanced", "long_texts", "conservative", "custom"):
            result = ModelRegistry._profile_to_limits(profile)
            assert result is not None
            assert hasattr(result, "request_limit")
            assert hasattr(result, "total_tokens_limit")

    def test_unknown_profile_returns_none(self) -> None:
        """Unbekanntes Profil gibt None zurück."""
        result = ModelRegistry._profile_to_limits("nonexistent")
        assert result is None

    def test_empty_profile_returns_none(self) -> None:
        """Leeres Profil gibt None zurück."""
        result = ModelRegistry._profile_to_limits("")
        assert result is None

    def test_quick_profile_low_limits(self) -> None:
        """'quick' Profil hat niedrige Limits."""
        result = ModelRegistry._profile_to_limits("quick")
        assert result is not None
        assert result.request_limit == 10
        assert result.total_tokens_limit == 16000

    def test_long_texts_profile_high_limits(self) -> None:
        """'long_texts' Profil hat hohe Limits."""
        result = ModelRegistry._profile_to_limits("long_texts")
        assert result is not None
        assert result.total_tokens_limit == 128000
