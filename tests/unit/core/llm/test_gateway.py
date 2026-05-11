"""Tests for llm/gateway.py"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare_core.llm.gateway import LLMGateway
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.result import LLMResult
from narrare_core.llm.retry import NO_RETRY
from narrare_core.shared.errors import (
    LLMAuthError,
    LLMContextTooLargeError,
    LLMGatewayError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)


@pytest.fixture
def gateway() -> LLMGateway:
    return LLMGateway(default_provider="anthropic")


class TestLLMGatewayClassifyError:
    def test_classifies_rate_limit(self, gateway: LLMGateway) -> None:
        err = Exception("429 Too Many Requests rate limit exceeded")
        result = gateway._classify_error(err)  # type: ignore[reportPrivateUsage]
        assert isinstance(result, LLMRateLimitError)

    def test_classifies_auth_error(self, gateway: LLMGateway) -> None:
        err = Exception("401 Unauthorized invalid api key")
        result = gateway._classify_error(err)  # type: ignore[reportPrivateUsage]
        assert isinstance(result, LLMAuthError)

    def test_classifies_timeout(self, gateway: LLMGateway) -> None:
        err = Exception("Request timed out after 30s")
        result = gateway._classify_error(err)  # type: ignore[reportPrivateUsage]
        assert isinstance(result, LLMTimeoutError)


class TestLLMGatewayRun:
    async def test_returns_llm_result_on_success(self, gateway: LLMGateway) -> None:
        # Mock the usage object with actual int attributes
        mock_usage = MagicMock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 50
        mock_usage.total_tokens = 60

        mock_result = MagicMock()
        mock_result.data = "Generated text."
        mock_result.usage.return_value = mock_usage
        mock_result.__str__ = lambda self: self.data  # type: ignore[misc]

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with patch.object(gateway, "_make_agent", return_value=mock_agent):
            result = await gateway.run(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write something.",
                retry_config=NO_RETRY,
            )

        assert isinstance(result, LLMResult)
        assert result.text == "Generated text."
        assert result.usage.total_tokens == 60
        assert result.intent == "write"

    async def test_raises_domain_error_on_failure(self, gateway: LLMGateway) -> None:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("401 Unauthorized invalid api key"))

        with (
            patch.object(gateway, "_make_agent", return_value=mock_agent),
            pytest.raises(LLMAuthError),
        ):
            await gateway.run(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                retry_config=NO_RETRY,
            )

    async def test_uses_model_override(self, gateway: LLMGateway) -> None:
        captured_model_id: list[str] = []

        def capture_model(model_id: str) -> MagicMock:
            captured_model_id.append(model_id)
            return MagicMock()

        # Mock the usage object with actual int attributes
        mock_usage = MagicMock()
        mock_usage.input_tokens = 5
        mock_usage.output_tokens = 10
        mock_usage.total_tokens = 15

        mock_result = MagicMock()
        mock_result.data = "text"
        mock_result.usage.return_value = mock_usage

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_result)

        with (
            patch.object(gateway, "_get_model", side_effect=capture_model),
            patch.object(gateway, "_make_agent", return_value=mock_agent),
        ):
            await gateway.run(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                model_override="glm-z1-32b",
                retry_config=NO_RETRY,
            )

        assert captured_model_id == ["glm-z1-32b"]


class TestLLMGatewayClassifyErrorAdditional:
    """Cover all branches of _classify_error."""

    def test_classifies_context_too_large(self, gateway: LLMGateway) -> None:
        err = Exception("context length exceeded maximum token limit")
        result = gateway._classify_error(err)  # type: ignore[reportPrivateUsage]
        assert isinstance(result, LLMContextTooLargeError)

    def test_classifies_service_unavailable(self, gateway: LLMGateway) -> None:
        err = Exception("503 Service overloaded unavailable")
        result = gateway._classify_error(err)  # type: ignore[reportPrivateUsage]
        assert isinstance(result, LLMServiceUnavailableError)

    def test_classifies_bad_gateway(self, gateway: LLMGateway) -> None:
        err = Exception("502 Bad Gateway capacity issue")
        result = gateway._classify_error(err)  # type: ignore[reportPrivateUsage]
        assert isinstance(result, LLMServiceUnavailableError)

    def test_classifies_invalid_request(self, gateway: LLMGateway) -> None:
        err = Exception("400 Bad Request invalid parameter")
        result = gateway._classify_error(err)  # type: ignore[reportPrivateUsage]
        assert isinstance(result, LLMInvalidRequestError)

    def test_classifies_generic_error_as_fallback(self, gateway: LLMGateway) -> None:
        err = Exception("something completely unexpected")
        result = gateway._classify_error(err)  # type: ignore[reportPrivateUsage]
        assert isinstance(result, LLMGatewayError)
        assert "Unexpected" in str(result)


class TestLLMGatewayStream:
    """Tests for the streaming method — covers lines 243-291."""

    async def test_stream_yields_text_chunks_and_final_chunk(self, gateway: LLMGateway) -> None:
        from narrare_core.llm.result import StreamChunk

        # Mock usage on the stream result
        mock_usage = MagicMock()
        mock_usage.input_tokens = 20
        mock_usage.output_tokens = 80
        mock_usage.total_tokens = 100

        # Mock stream_text as an async generator yielding text deltas
        async def fake_stream_text(**kwargs: object) -> object:
            for chunk in ["Hello", " world", "!"]:
                yield chunk

        mock_stream_result = MagicMock()
        mock_stream_result.stream_text = fake_stream_text
        mock_stream_result.usage.return_value = mock_usage

        # Mock run_stream to return an async context manager
        mock_agent = MagicMock()

        class FakeStreamContext:
            async def __aenter__(self) -> MagicMock:
                return mock_stream_result

            async def __aexit__(self, *args: object) -> None:
                pass

        mock_agent.run_stream = MagicMock(return_value=FakeStreamContext())

        with patch.object(gateway, "_make_agent", return_value=mock_agent):
            chunks: list[StreamChunk] = []
            async for chunk in gateway.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
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

    async def test_stream_raises_domain_error_on_failure(self, gateway: LLMGateway) -> None:
        mock_agent = MagicMock()

        class FailingStreamContext:
            async def __aenter__(self) -> None:
                raise Exception("503 Service unavailable")

            async def __aexit__(self, *args: object) -> None:
                pass

        mock_agent.run_stream = MagicMock(return_value=FailingStreamContext())

        with (
            patch.object(gateway, "_make_agent", return_value=mock_agent),
            pytest.raises(LLMServiceUnavailableError),
        ):
            async for _ in gateway.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
            ):
                pass  # should never reach here

    async def test_stream_uses_model_override(self, gateway: LLMGateway) -> None:
        captured_model_ids: list[str] = []

        def capture_model(model_id: str) -> MagicMock:
            captured_model_ids.append(model_id)
            return MagicMock()

        mock_usage = MagicMock()
        mock_usage.input_tokens = 0
        mock_usage.output_tokens = 0
        mock_usage.total_tokens = 0

        async def empty_stream(**kwargs: object) -> object:
            return
            yield  # type: ignore[misc]  # make it an async generator

        mock_stream_result = MagicMock()
        mock_stream_result.stream_text = empty_stream
        mock_stream_result.usage.return_value = mock_usage

        mock_agent = MagicMock()

        class FakeStreamContext:
            async def __aenter__(self) -> MagicMock:
                return mock_stream_result

            async def __aexit__(self, *args: object) -> None:
                pass

        mock_agent.run_stream = MagicMock(return_value=FakeStreamContext())

        with (
            patch.object(gateway, "_get_model", side_effect=capture_model),
            patch.object(gateway, "_make_agent", return_value=mock_agent),
        ):
            async for _ in gateway.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                model_override="gpt-4o",
            ):
                pass

        assert captured_model_ids == ["gpt-4o"]
