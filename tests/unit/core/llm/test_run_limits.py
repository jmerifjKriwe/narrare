"""Tests for ADR-045 run-limit resolution and enforcement."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.result import StreamedRunResult
from pydantic_ai.usage import RunUsage, UsageLimits

from narrare_core.ai_invocation.budgets import OutputBudget, OutputBudgetDecision
from narrare_core.llm import LLMIntent, ModelLimits, ResolvedModelConfig
from narrare_core.llm.run_limits import DefaultRunLimitResolver, profile_to_usage_limits

if TYPE_CHECKING:
    from narrare_core.llm.gateway import ModelRegistry


def _budget(max_tokens: int, profile: str) -> OutputBudgetDecision:
    return OutputBudgetDecision(
        budget=OutputBudget(max_tokens=max_tokens, profile=profile),
        source="test",
        reason="test budget",
    )


class TestDefaultRunLimitResolver:
    def test_resolves_budget_to_usage_limits_and_model_settings(self) -> None:
        resolver = DefaultRunLimitResolver(model_limits_provider=lambda _provider, _model: None)
        config = ResolvedModelConfig(provider_name="anthropic", model_id="claude", max_tokens=4096)

        limits = resolver.resolve(
            config=config,
            budget=_budget(16000, "comprehensive"),
            invocation_id=uuid4(),
        )

        assert limits.output_budget_profile == "comprehensive"
        assert limits.effective_output_tokens == 16000
        assert limits.usage_limits is not None
        assert limits.usage_limits.output_tokens_limit == 16000
        assert limits.model_settings["max_tokens"] == 16000

    def test_caps_to_known_provider_max_output(self) -> None:
        resolver = DefaultRunLimitResolver(
            model_limits_provider=lambda _provider, _model: ModelLimits(context=200000, output=4096)
        )
        config = ResolvedModelConfig(provider_name="anthropic", model_id="claude", max_tokens=4096)

        limits = resolver.resolve(
            config=config,
            budget=_budget(16000, "comprehensive"),
            invocation_id=uuid4(),
        )

        assert limits.provider_max_output_tokens == 4096
        assert limits.effective_output_tokens == 4096
        assert limits.source == "test:capped_to_provider_max"


class TestModelRegistryLimitEnforcement:
    async def test_run_passes_resolved_usage_limits_and_model_settings(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        mock_result = MagicMock(
            spec=AgentRunResult,
            output="mocked",
            usage=MagicMock(spec=RunUsage, input_tokens=1, output_tokens=1, total_tokens=2),
        )
        mock_run = AsyncMock(return_value=mock_result)

        with patch.object(Agent, "run", mock_run):
            await registry_with_test_model.run(
                LLMIntent.WRITE,
                prompt="Write.",
                config=write_config,
                usage_limits=UsageLimits(output_tokens_limit=8000),
            )

        _args, kwargs = mock_run.call_args
        assert kwargs["usage_limits"].output_tokens_limit == 8000
        assert kwargs["model_settings"]["max_tokens"] == 8000

    async def test_stream_passes_resolved_usage_limits_and_model_settings(
        self,
        registry_with_test_model: ModelRegistry,
        write_config: ResolvedModelConfig,
    ) -> None:
        async def mock_stream_text(delta: bool = True):
            if delta:
                yield "chunk"

        mock_stream_result = MagicMock(spec=StreamedRunResult)
        mock_stream_result.stream_text = mock_stream_text
        mock_stream_result.usage = MagicMock(
            spec=RunUsage,
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
        )
        mock_context = MagicMock(spec=AbstractAsyncContextManager)
        mock_context.__aenter__ = AsyncMock(return_value=mock_stream_result)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_run_stream = MagicMock(spec=Agent.run_stream, return_value=mock_context)

        with patch.object(Agent, "run_stream", mock_run_stream):
            async for _chunk in registry_with_test_model.stream(
                intent=LLMIntent.WRITE,
                system_prompt="System.",
                user_prompt="Write.",
                config=write_config,
                usage_limits=UsageLimits(output_tokens_limit=500),
            ):
                pass

        _args, kwargs = mock_run_stream.call_args
        assert kwargs["usage_limits"].output_tokens_limit == 500
        assert kwargs["model_settings"]["max_tokens"] == 500


def test_comprehensive_profile_is_recognized_by_gateway_profile_mapping() -> None:
    limits = profile_to_usage_limits("comprehensive")

    assert limits is not None
    total = limits.total_tokens_limit
    assert total is not None
    assert total > 128000


def test_suggest_max_tokens_is_immutable_ux_cap() -> None:
    """SUGGEST_MAX_TOKENS is an immutable UX latency constraint.

    Changing this value requires re-validating the <500ms latency
    target (ADR-045 D3 C). This test exists to force explicit
    review of any change.
    """
    from narrare_core.llm.run_limits import SUGGEST_MAX_TOKENS

    assert SUGGEST_MAX_TOKENS == 60


class TestMergeModelSettings:
    """``merge_model_settings`` merges cache/provider settings with run limits."""

    def test_returns_none_when_both_none(self) -> None:
        from narrare_core.llm.run_limits import merge_model_settings

        assert merge_model_settings(None, None) is None

    def test_base_only_passes_through(self) -> None:
        from narrare_core.llm.run_limits import merge_model_settings

        assert merge_model_settings({"temperature": 0.7}, None) == {"temperature": 0.7}

    def test_limits_only_applies_model_settings(self) -> None:
        from narrare_core.llm.run_limits import ResolvedRunLimits, merge_model_settings

        limits = MagicMock(spec=ResolvedRunLimits)
        limits.model_settings = {"max_tokens": 100}
        assert merge_model_settings(None, limits) == {"max_tokens": 100}

    def test_limits_override_base_values(self) -> None:
        from narrare_core.llm.run_limits import ResolvedRunLimits, merge_model_settings

        limits = MagicMock(spec=ResolvedRunLimits)
        limits.model_settings = {"max_tokens": 200}
        result = merge_model_settings({"max_tokens": 50, "temperature": 0.5}, limits)
        assert result == {"max_tokens": 200, "temperature": 0.5}


class TestResolveRuntimeLimits:
    """``resolve_runtime_limits`` short-circuits pre-resolved limits and skips
    resolution when neither budget nor profile is set."""

    def test_pre_resolved_limits_returned_unchanged(self) -> None:
        from narrare_core.llm.run_limits import resolve_runtime_limits

        resolver = DefaultRunLimitResolver(model_limits_provider=lambda _p, _m: None)
        config = ResolvedModelConfig(provider_name="anthropic", model_id="claude", max_tokens=4096)
        pre = resolver.resolve(
            config=config, budget=_budget(1000, "balanced"), invocation_id=uuid4()
        )

        result = resolve_runtime_limits(
            resolver, config=config, resolved_limits=pre, output_budget=None
        )

        assert result is pre

    def test_returns_none_when_no_budget_and_no_profile(self) -> None:
        from narrare_core.llm.run_limits import resolve_runtime_limits

        resolver = DefaultRunLimitResolver(model_limits_provider=lambda _p, _m: None)
        config = ResolvedModelConfig(provider_name="anthropic", model_id="claude", max_tokens=4096)

        result = resolve_runtime_limits(
            resolver, config=config, resolved_limits=None, output_budget=None
        )

        assert result is None

    def test_resolves_from_budget_when_not_pre_resolved(self) -> None:
        from narrare_core.llm.run_limits import resolve_runtime_limits

        resolver = DefaultRunLimitResolver(model_limits_provider=lambda _p, _m: None)
        config = ResolvedModelConfig(provider_name="anthropic", model_id="claude", max_tokens=4096)

        result = resolve_runtime_limits(
            resolver,
            config=config,
            resolved_limits=None,
            output_budget=_budget(2000, "balanced"),
        )

        assert result is not None
        assert result.effective_output_tokens == 2000
