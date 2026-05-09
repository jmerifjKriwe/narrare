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
    LLMRateLimitError,
    LLMTimeoutError,
)


@pytest.fixture
def gateway() -> LLMGateway:
    return LLMGateway(default_provider="anthropic")


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
    async def test_returns_llm_result_on_success(self, gateway: LLMGateway) -> None:
        mock_usage = MagicMock()
        mock_usage.request_tokens = 10
        mock_usage.response_tokens = 50
        mock_usage.total_tokens = 60

        mock_result = MagicMock()
        mock_result.data = "Generated text."
        mock_result.usage.return_value = mock_usage

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

        with patch.object(gateway, "_make_agent", return_value=mock_agent):
            with pytest.raises(LLMAuthError):
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

        mock_usage = MagicMock()
        mock_usage.request_tokens = 5
        mock_usage.response_tokens = 10
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
