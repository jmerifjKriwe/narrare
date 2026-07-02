"""Tests for narrare_core.llm.result — LLM call result dataclasses."""

from __future__ import annotations

from narrare_core.llm.result import LLMResult, TokenUsage


def _usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)


class TestLLMResultOk:
    """``LLMResult.ok`` reflects whether non-empty text was produced."""

    def test_ok_true_when_text_present(self) -> None:
        result = LLMResult(text="hello", usage=_usage(), model="gpt-4o", intent="write")
        assert result.ok is True

    def test_ok_false_when_text_empty(self) -> None:
        result = LLMResult(text="", usage=_usage(), model="gpt-4o", intent="write")
        assert result.ok is False


class TestTokenUsageCostEstimate:
    """``cost_estimate_usd`` falls back to the blended rate without provider/model."""

    def test_blended_fallback_when_no_provider_or_model(self) -> None:
        # 30 total tokens * $3 / 1M = $0.00009
        assert _usage().cost_estimate_usd == 30 * 0.000003
