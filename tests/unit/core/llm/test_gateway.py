"""Tests for llm/gateway.py — ModelRegistry run() and stream() methods."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pydantic_ai.models.test import TestModel

    from narrare_core.llm.result import StreamChunk

from narrare_core.llm import LLMIntent, ResolvedModelConfig
from narrare_core.llm.gateway import ModelRegistry


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


class TestModelRegistryPrepare:
    """ModelRegistry.prepare() — the single assembly point for a call."""

    async def test_prepare_returns_coherent_triple(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
        test_model: TestModel,
    ) -> None:
        """prepare() returns a PreparedModelCall bundling model + settings + limits."""
        from narrare_core.llm._prepared_call import PreparedModelCall

        prepared = await registry_with_test_model.prepare(write_config)

        assert isinstance(prepared, PreparedModelCall)
        assert prepared.model is test_model
        # No intent, no cache, no usage_limits → settings and limits are None.
        assert prepared.model_settings is None
        assert prepared.usage_limits is None

    async def test_prepare_intent_flows_to_thinking_policy(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """prepare(intent=...) resolves the thinking level via the intent policy."""
        prepared = await registry_with_test_model.prepare(write_config, intent=LLMIntent.KB_EXTRACT)

        # KB category → thinking "low" (intent-aware thinking policy).
        assert prepared.model_settings == {"thinking": "low"}

    async def test_prepare_write_intent_without_cache_returns_none_settings(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """WRITING intent omits thinking; without cache settings the triple has None."""
        prepared = await registry_with_test_model.prepare(write_config, intent=LLMIntent.WRITE)

        assert prepared.model_settings is None

    async def test_prepare_passes_credentials_to_get_model(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """prepare() forwards api_key/base_url to get_model."""
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
            prepared = await registry_with_test_model.prepare(
                write_config,
                api_key="sk-test-key",
                base_url="https://custom.api/v1",
            )

        assert captured_kwargs[0]["api_key"] == "sk-test-key"
        assert captured_kwargs[0]["base_url"] == "https://custom.api/v1"
        assert prepared.model is not None

    async def test_prepare_usage_limits_pass_through_to_triple(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """prepare(usage_limits=...) returns the limits and forwards the output cap."""
        from pydantic_ai.usage import UsageLimits

        limits = UsageLimits(output_tokens_limit=500)

        prepared = await registry_with_test_model.prepare(write_config, usage_limits=limits)

        assert prepared.usage_limits is limits
        # ADR-045: the output cap is mirrored as model_settings["max_tokens"].
        assert prepared.model_settings == {"max_tokens": 500}


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
        for profile in ("quick", "balanced", "long_texts", "comprehensive", "custom"):
            result = ModelRegistry._profile_to_limits(profile)
            assert result is not None
            assert hasattr(result, "request_limit")
            assert hasattr(result, "total_tokens_limit")

    def test_legacy_conservative_profile_maps_to_balanced_limits(self) -> None:
        """Compatibility boundary maps retired conservative values to balanced."""
        result = ModelRegistry._profile_to_limits("conservative")

        assert result is not None
        assert result.request_limit == 25
        assert result.total_tokens_limit == 64000

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


class TestModelRegistryPassesCacheSettings:
    """ModelRegistry.run/stream gibt model_settings an Agent.run/run_stream weiter."""

    async def test_run_without_cache_does_not_pass_model_settings(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        """write_config (cache=None) → model_settings=None an Agent.run."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from pydantic_ai import Agent
        from pydantic_ai.agent import AgentRunResult
        from pydantic_ai.usage import RunUsage

        mock_result = MagicMock(
            spec=AgentRunResult,
            output="mocked",
            usage=MagicMock(spec=RunUsage, input_tokens=0, output_tokens=0, total_tokens=0),
        )
        mock_run = AsyncMock(return_value=mock_result)

        with patch.object(Agent, "run", mock_run):
            await registry_with_test_model.run(
                LLMIntent.WRITE,
                prompt="Write.",
                config=write_config,
            )

        mock_run.assert_called_once()
        _args, kwargs = mock_run.call_args
        assert kwargs.get("model_settings") is None

    async def test_run_with_anthropic_cache_passes_model_settings(
        self,
        registry_with_test_model: ModelRegistry,
    ) -> None:
        """Anthropic CacheSettings → model_settings={"cache_control": True}."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from pydantic_ai import Agent
        from pydantic_ai.agent import AgentRunResult
        from pydantic_ai.usage import RunUsage

        from narrare_core.llm import CacheSettings

        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            temperature=0.8,
            max_tokens=4096,
            streams=True,
            cache=CacheSettings(),
        )

        mock_result = MagicMock(
            spec=AgentRunResult,
            output="mocked",
            usage=MagicMock(spec=RunUsage, input_tokens=0, output_tokens=0, total_tokens=0),
        )
        mock_run = AsyncMock(return_value=mock_result)

        with patch.object(Agent, "run", mock_run):
            await registry_with_test_model.run(
                LLMIntent.WRITE,
                prompt="Write with cache.",
                config=config,
            )

        mock_run.assert_called_once()
        _args, kwargs = mock_run.call_args
        assert kwargs.get("model_settings") == {"cache_control": True}

    async def test_stream_with_anthropic_cache_passes_model_settings(
        self,
        registry_with_test_model: ModelRegistry,
    ) -> None:
        """Anthropic CacheSettings → model_settings an agent.run_stream."""
        from contextlib import AbstractAsyncContextManager
        from unittest.mock import AsyncMock, MagicMock, patch

        from pydantic_ai import Agent
        from pydantic_ai.result import StreamedRunResult
        from pydantic_ai.usage import RunUsage

        from narrare_core.llm import CacheSettings

        config = ResolvedModelConfig(
            provider_name="anthropic",
            model_id="claude-sonnet-4-5-20251020",
            temperature=0.8,
            max_tokens=4096,
            streams=True,
            cache=CacheSettings(),
        )

        async def mock_stream_text(delta=True):  # type: ignore[no-untyped-def]
            for _ in range(0):  # empty — yields nothing
                yield ""

        mock_stream_result = MagicMock(spec=StreamedRunResult)
        mock_stream_result.stream_text = mock_stream_text
        mock_stream_result.usage = MagicMock(
            spec=RunUsage,
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
        )

        # Async context manager for agent.run_stream() return value
        mock_context = MagicMock(spec=AbstractAsyncContextManager)
        mock_context.__aenter__ = AsyncMock(return_value=mock_stream_result)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_run_stream = MagicMock(spec=Agent.run_stream, return_value=mock_context)

        with patch.object(Agent, "run_stream", mock_run_stream):
            async for _chunk in registry_with_test_model.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write with cache.",
                config=config,
            ):
                pass

        mock_run_stream.assert_called_once()
        _args, kwargs = mock_run_stream.call_args
        assert kwargs.get("model_settings") == {"cache_control": True}
