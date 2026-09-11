"""Tests for BetaReaderAgent.run_phase2 kwargs pass-through.

Pins the Task-1 core pass-through: ``run_phase2`` accepts
``model_settings``/``usage_limits`` (the settings half of the
``ModelRegistry.prepare()`` triple) and forwards them to the ephemeral
phase-2 agent's run — mirroring ``run_phase1`` (Task 6d).

Test strategy:
- The real BetaReaderAgent is instantiated with TestModel (RULE-01b)
- ``NarrareAgent.run`` is patched so the ephemeral phase-2 agent's run
  is observable without a real LLM call
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.beta_reader_agent import BetaReaderAgent
from narrare_core.agents.beta_reader_types import (
    BetaReaderDeps,
    BetaReaderPhase2Output,
)

_SENTINEL_SETTINGS: ModelSettings = ModelSettings(max_tokens=12_345)
_SENTINEL_LIMITS = UsageLimits(request_limit=7)


def _phase2_output() -> BetaReaderPhase2Output:
    return BetaReaderPhase2Output(
        detailed_feedback=[],
        revision_suggestions=[],
        category_score=5,
    )


class TestRunPhase2Settings:
    """run_phase2 forwards model_settings/usage_limits to the inner run."""

    @pytest.mark.asyncio
    async def test_forwards_settings_and_limits(self) -> None:
        agent = BetaReaderAgent(model=TestModel())
        deps = BetaReaderDeps(chapter_text="Test chapter content.")
        expected = _phase2_output()

        with patch.object(NarrareAgent, "run", new=AsyncMock(return_value=expected)) as mock_run:
            result = await agent.run_phase2(
                "Deep-dive on plot",
                deps,
                model=TestModel(),
                system_prompt="Phase 2 prompt.",
                model_settings=_SENTINEL_SETTINGS,
                usage_limits=_SENTINEL_LIMITS,
            )

        assert result is expected
        kwargs = mock_run.call_args.kwargs
        assert kwargs["model_settings"] is _SENTINEL_SETTINGS
        assert kwargs["usage_limits"] is _SENTINEL_LIMITS

    @pytest.mark.asyncio
    async def test_defaults_to_none(self) -> None:
        """Without kwargs the inner run receives None (backward compat)."""
        agent = BetaReaderAgent(model=TestModel())
        deps = BetaReaderDeps(chapter_text="Test chapter content.")
        expected = _phase2_output()

        with patch.object(NarrareAgent, "run", new=AsyncMock(return_value=expected)) as mock_run:
            result = await agent.run_phase2("Deep-dive", deps, model=TestModel())

        assert result is expected
        kwargs = mock_run.call_args.kwargs
        assert kwargs["model_settings"] is None
        assert kwargs["usage_limits"] is None
