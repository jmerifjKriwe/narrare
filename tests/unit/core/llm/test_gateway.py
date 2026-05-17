"""Tests for llm/gateway.py — using pydantic-ai TestModel where possible."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

# narrare: allow reason="gateway tests use TestModel instead of real LLM"
from pydantic_ai.models.test import (
    TestModel,
)

if TYPE_CHECKING:
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
        gateway_with_test_model: LLMGateway,
        write_config: ResolvedModelConfig,
    ) -> None:
        """Gateway returns LLMResult when Agent succeeds."""
        result = await gateway_with_test_model.run(
            intent=LLMIntent.WRITE,
            system_prompt="System.",
            user_prompt="Write something.",
            config=write_config,
            retry_config=NO_RETRY,
        )

        assert isinstance(result, LLMResult)
        assert result.text == "Test response from pydantic-ai TestModel."
        assert result.usage.total_tokens > 0
        assert result.intent == "write"

    async def test_raises_domain_error_on_failure(
        self,
        gateway_with_test_model: LLMGateway,
        write_config: ResolvedModelConfig,
    ) -> None:
        """Gateway raises LLMGatewayError when Agent fails."""
        # narrare: allow reason="testing error classification with pydantic-ai exception"
        from pydantic_ai.exceptions import (
            ModelHTTPError,
        )

        # narrare: allow reason="testing error handling with FunctionModel"
        from pydantic_ai.models.function import (
            FunctionModel,
        )

        def raise_auth_error(messages, info):
            raise ModelHTTPError(status_code=401, model_name="test")

        error_model = FunctionModel(raise_auth_error)

        with (
            patch.object(
                gateway_with_test_model,
                "_get_model_with_credentials",
                return_value=error_model,
            ),
            pytest.raises(LLMAuthError),
        ):
            await gateway_with_test_model.run(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=write_config,
                retry_config=NO_RETRY,
            )

    async def test_uses_config_provider_and_model(
        self,
        gateway_with_test_model: LLMGateway,
    ) -> None:
        """Gateway passes provider_name and model_id to factory."""
        captured_args: list[tuple[str, str]] = []

        def capture_model(provider_name: str, model_id: str, **kwargs: object) -> object:
            captured_args.append((provider_name, model_id))
            return TestModel(custom_output_text="captured")

        config = ResolvedModelConfig(provider_name="zai", model_id="glm-z1-32b")

        with patch.object(
            gateway_with_test_model,
            "_get_model_with_credentials",
            side_effect=capture_model,
        ):
            await gateway_with_test_model.run(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=config,
                retry_config=NO_RETRY,
            )

        assert captured_args == [("zai", "glm-z1-32b")]

    async def test_passes_credentials_to_factory(
        self,
        gateway_with_test_model: LLMGateway,
    ) -> None:
        """Gateway passes api_key and base_url to factory."""
        captured_kwargs: list[dict[str, object]] = []

        def capture_credentials(provider_name: str, model_id: str, **kwargs: object) -> object:
            captured_kwargs.append(kwargs)
            return TestModel(custom_output_text="captured")

        config = ResolvedModelConfig(provider_name="openrouter", model_id="gpt-4o")

        with patch.object(
            gateway_with_test_model,
            "_get_model_with_credentials",
            side_effect=capture_credentials,
        ):
            await gateway_with_test_model.run(
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
        gateway_with_test_model: LLMGateway,
        write_config: ResolvedModelConfig,
    ) -> None:
        # narrare: allow reason="testing stream error classification with pydantic-ai exception"
        from pydantic_ai.exceptions import (
            ModelHTTPError,
        )

        # narrare: allow reason="testing stream error handling with FunctionModel"
        from pydantic_ai.models.function import (
            FunctionModel,
        )

        def raise_unavailable(messages, info):
            raise ModelHTTPError(status_code=503, model_name="test")

        async def raise_on_stream(messages, info):
            raise ModelHTTPError(status_code=503, model_name="test")
            yield  # noqa: unreachable — makes this an async generator

        error_model = FunctionModel(raise_unavailable, stream_function=raise_on_stream)

        with (
            patch.object(
                gateway_with_test_model,
                "_get_model_with_credentials",
                return_value=error_model,
            ),
            pytest.raises(LLMServiceUnavailableError),
        ):
            async for _ in gateway_with_test_model.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=write_config,
            ):
                pass

    async def test_stream_uses_config_provider_and_model(
        self,
        gateway_with_test_model: LLMGateway,
    ) -> None:
        captured_args: list[tuple[str, str]] = []

        def capture_model(provider_name: str, model_id: str, **kwargs: object) -> object:
            captured_args.append((provider_name, model_id))
            return TestModel(custom_output_text="captured")

        config = ResolvedModelConfig(provider_name="openai", model_id="gpt-4o")

        with patch.object(
            gateway_with_test_model,
            "_get_model_with_credentials",
            side_effect=capture_model,
        ):
            async for _ in gateway_with_test_model.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=config,
            ):
                pass

        assert captured_args == [("openai", "gpt-4o")]
