"""Tests for llm/gateway.py — using FakePydanticAgent instead of MagicMock chains."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from narrare_core.llm.gateway import LLMGateway
from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import LLMResult
from narrare_core.llm.retry import NO_RETRY
from narrare_core.shared.errors import (
    LLMAuthError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)
from tests.fakes.fake_pydantic_agent import FakePydanticAgent


@pytest.fixture
def gateway() -> LLMGateway:
    return LLMGateway(default_provider="anthropic")


@pytest.fixture
def write_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.8,
        max_tokens=4096,
        streams=True,
    )


class TestLLMGatewayClassifyError:
    def test_classifies_rate_limit(self, gateway: LLMGateway) -> None:
        err = Exception("429 Too Many Requests rate limit exceeded")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMRateLimitError)

    def test_classifies_auth_error(self, gateway: LLMGateway) -> None:
        err = Exception("401 Unauthorized invalid api key")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMAuthError)

    def test_classifies_timeout(self, gateway: LLMGateway) -> None:
        err = Exception("Request timed out after 30s")
        result = gateway._classify_error(err)
        assert isinstance(result, LLMTimeoutError)


class TestLLMGatewayRun:
    async def test_returns_llm_result_on_success(
        self,
        gateway: LLMGateway,
        write_config: ResolvedModelConfig,
    ) -> None:
        fake_agent = FakePydanticAgent()
        fake_agent.returns("Generated text.", input_tokens=10, output_tokens=50)

        with (
            patch.object(gateway, "_get_model_with_credentials", return_value=object()),
            patch.object(gateway, "_make_agent", return_value=fake_agent),
        ):
            result = await gateway.run(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write something.",
                config=write_config,
                retry_config=NO_RETRY,
            )

        assert isinstance(result, LLMResult)
        assert result.text == "Generated text."
        assert result.usage.total_tokens == 60
        assert result.intent == "write"

    async def test_raises_domain_error_on_failure(
        self,
        gateway: LLMGateway,
        write_config: ResolvedModelConfig,
    ) -> None:
        fake_agent = FakePydanticAgent()
        fake_agent.raises(Exception("401 Unauthorized invalid api key"))

        with (
            patch.object(gateway, "_get_model_with_credentials", return_value=object()),
            patch.object(gateway, "_make_agent", return_value=fake_agent),
            pytest.raises(LLMAuthError),
        ):
            await gateway.run(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=write_config,
                retry_config=NO_RETRY,
            )

    async def test_uses_config_provider_and_model(
        self,
        gateway: LLMGateway,
    ) -> None:
        captured_args: list[tuple[str, str]] = []

        def capture_model(provider_name: str, model_id: str, **kwargs: object) -> object:
            captured_args.append((provider_name, model_id))
            return object()

        fake_agent = FakePydanticAgent()
        fake_agent.returns("text", input_tokens=5, output_tokens=10)

        config = ResolvedModelConfig(provider_name="zai", model_id="glm-z1-32b")

        with (
            patch.object(gateway, "_get_model_with_credentials", side_effect=capture_model),
            patch.object(gateway, "_make_agent", return_value=fake_agent),
        ):
            await gateway.run(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=config,
                retry_config=NO_RETRY,
            )

        assert captured_args == [("zai", "glm-z1-32b")]

    async def test_passes_credentials_to_factory(
        self,
        gateway: LLMGateway,
    ) -> None:
        captured_kwargs: list[dict[str, object]] = []

        def capture_credentials(provider_name: str, model_id: str, **kwargs: object) -> object:
            captured_kwargs.append(kwargs)
            return object()

        fake_agent = FakePydanticAgent()
        fake_agent.returns("text", input_tokens=5, output_tokens=10)

        config = ResolvedModelConfig(provider_name="openrouter", model_id="gpt-4o")

        with (
            patch.object(gateway, "_get_model_with_credentials", side_effect=capture_credentials),
            patch.object(gateway, "_make_agent", return_value=fake_agent),
        ):
            await gateway.run(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=config,
                api_key="sk-or-test-key",
                base_url="https://openrouter.ai/api/v1",
                retry_config=NO_RETRY,
            )

        assert captured_kwargs[0]["api_key"] == "sk-or-test-key"
        assert captured_kwargs[0]["base_url"] == "https://openrouter.ai/api/v1"


class TestLLMGatewayStream:
    """Tests for the streaming method."""

    async def test_stream_yields_text_chunks_and_final_chunk(
        self,
        gateway: LLMGateway,
        write_config: ResolvedModelConfig,
    ) -> None:
        from narrare_core.llm.result import StreamChunk

        fake_agent = FakePydanticAgent()
        fake_agent.returns_stream(["Hello", " world", "!"], input_tokens=20, output_tokens=80)

        with (
            patch.object(gateway, "_get_model_with_credentials", return_value=object()),
            patch.object(gateway, "_make_agent", return_value=fake_agent),
        ):
            chunks: list[StreamChunk] = []
            async for chunk in gateway.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=write_config,
            ):
                chunks.append(chunk)

        # Should have 3 text chunks + 1 final chunk
        assert len(chunks) == 4
        assert chunks[0].text == "Hello"
        assert chunks[1].text == " world"
        assert chunks[2].text == "!"
        assert chunks[3].is_final is True
        assert chunks[3].text == ""
        assert chunks[3].usage is not None
        assert chunks[3].usage.total_tokens == 100

    async def test_stream_raises_domain_error_on_failure(
        self,
        gateway: LLMGateway,
        write_config: ResolvedModelConfig,
    ) -> None:
        fake_agent = FakePydanticAgent()
        fake_agent.raises_on_stream(Exception("503 Service unavailable"))

        with (
            patch.object(gateway, "_get_model_with_credentials", return_value=object()),
            patch.object(gateway, "_make_agent", return_value=fake_agent),
            pytest.raises(LLMServiceUnavailableError),
        ):
            async for _ in gateway.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=write_config,
            ):
                pass  # should never reach here

    async def test_stream_uses_config_provider_and_model(
        self,
        gateway: LLMGateway,
    ) -> None:
        captured_args: list[tuple[str, str]] = []

        def capture_model(provider_name: str, model_id: str, **kwargs: object) -> object:
            captured_args.append((provider_name, model_id))
            return object()

        fake_agent = FakePydanticAgent()
        fake_agent.returns_stream([])  # empty stream

        config = ResolvedModelConfig(provider_name="openai", model_id="gpt-4o")

        with (
            patch.object(gateway, "_get_model_with_credentials", side_effect=capture_model),
            patch.object(gateway, "_make_agent", return_value=fake_agent),
        ):
            async for _ in gateway.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=config,
            ):
                pass

        assert captured_args == [("openai", "gpt-4o")]
