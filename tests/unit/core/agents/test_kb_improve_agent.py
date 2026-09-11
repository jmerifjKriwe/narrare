"""Tests for agents/kb_improve_agent.py — Instantiation.

Test-Strategie:
- TestModel for deterministic agent tests
- Validator tested directly via _validate_output (test_kb_improve_validation.py)
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.kb_improve_agent import KBImproveAgent
from narrare_core.agents.kb_improve_types import KBImproveDeps, KBImproveOutput

# ---------------------------------------------------------------------------
# A. KBImproveAgent — Instantiation
# ---------------------------------------------------------------------------


class TestKBImproveAgentInstantiation:
    """KBImproveAgent can be instantiated with and without KBAgent."""

    def test_instantiation_without_kb_agent(self) -> None:
        agent = KBImproveAgent(model=TestModel())
        assert isinstance(agent, KBImproveAgent)
        assert agent._agent is not None

    def test_instantiation_with_system_prompt(self) -> None:
        agent = KBImproveAgent(
            model=TestModel(),
            system_prompt="You are a KB improvement analyzer.",
        )
        assert isinstance(agent, KBImproveAgent)


# ---------------------------------------------------------------------------
# B. Agent run — TestModel returns KBImproveOutput
# ---------------------------------------------------------------------------


class TestAgentRun:
    """Agent.run() with TestModel returns structured output.

    TestModel generates a placeholder suggestion for the required
    ``suggestions`` field, so only the output type is asserted.
    """

    @pytest.mark.asyncio
    async def test_run_returns_kb_improve_output(self) -> None:
        result = await KBImproveAgent(model=TestModel()).run(
            prompt="Analyze this entry", deps=KBImproveDeps()
        )
        assert isinstance(result, KBImproveOutput)
