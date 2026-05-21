"""Tests for PreferenceAnalysisAgent._process_analysis output function.

Extracted from test_preference_analysis_agent.py per RULE-04 (file size limit).
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.preference_analysis_agent import (
    PreferenceAnalysisAgent,
    PreferenceAnalysisDeps,
)


class TestProcessAnalysis:
    """Output Function is executed correctly."""

    @pytest.fixture()
    def run_context(self) -> RunContext[PreferenceAnalysisDeps]:
        return RunContext[PreferenceAnalysisDeps](
            deps=PreferenceAnalysisDeps(), model=TestModel(), usage=RunUsage()
        )

    @pytest.mark.asyncio
    async def test_process_analysis_with_values(
        self, run_context: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        result = await PreferenceAnalysisAgent(model=TestModel())._process_analysis(
            run_context,
            style_patterns=["concise", "active voice"],
            content_patterns=["dialogue-heavy"],
            avoidance_patterns=["purple prose"],
            confidence=0.8,
            summary="User prefers concise, dialogue-driven prose.",
        )
        assert len(result.style_patterns) == 2
        assert len(result.content_patterns) == 1
        assert len(result.avoidance_patterns) == 1
        assert result.confidence == 0.8
        assert "concise" in result.summary

    @pytest.mark.asyncio
    async def test_process_analysis_partial_streaming(
        self, run_context: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        run_context.partial_output = True
        result = await PreferenceAnalysisAgent(model=TestModel())._process_analysis(
            run_context,
            style_patterns=["test"],
            summary="Partial summary.",
        )
        assert result.style_patterns == []
        assert result.summary == ""

    @pytest.mark.asyncio
    async def test_process_analysis_empty(
        self, run_context: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        result = await PreferenceAnalysisAgent(model=TestModel())._process_analysis(run_context)
        assert result.style_patterns == []
        assert result.content_patterns == []
        assert result.avoidance_patterns == []
        assert result.confidence == 0.0
        assert result.summary == ""

    @pytest.mark.asyncio
    async def test_process_analysis_defaults_for_none_lists(
        self, run_context: RunContext[PreferenceAnalysisDeps]
    ) -> None:
        result = await PreferenceAnalysisAgent(model=TestModel())._process_analysis(
            run_context,
            style_patterns=None,
            content_patterns=None,
            avoidance_patterns=None,
        )
        assert result.style_patterns == []
        assert result.content_patterns == []
        assert result.avoidance_patterns == []
