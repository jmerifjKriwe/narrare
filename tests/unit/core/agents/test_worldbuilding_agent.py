"""Tests for agents/worldbuilding_agent.py — Instantiation and Deps.

Test-Strategie:
- TestModel for deterministic agent tests
- Validator tests live in ``test_worldbuilding_validation.py`` (ADR-035)
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.worldbuilding_agent import WorldbuildingAgent
from narrare_core.agents.worldbuilding_types import (
    WorldbuildingDeps,
    WorldbuildingPhase2Output,
)

# ---------------------------------------------------------------------------
# A. WorldbuildingDeps
# ---------------------------------------------------------------------------


class TestWorldbuildingDeps:
    """WorldbuildingDeps defaults and custom values."""

    def test_defaults(self) -> None:
        deps = WorldbuildingDeps()
        assert deps.language == "en"
        assert deps.entity_summaries == []
        assert deps.entity_details == {}
        assert deps.template_structures == {}
        assert deps.existing_relationships == []
        assert deps.available_rel_types == {}
        assert deps.world_context == ""
        assert deps.chapter_entity_refs == {}
        assert deps.candidate_pairs == []

    def test_custom_values(self) -> None:
        deps = WorldbuildingDeps(
            language="de",
            world_context="A fantasy world with dragons.",
            candidate_pairs=[("ent-1", "ent-2")],
        )
        assert deps.language == "de"
        assert "dragons" in deps.world_context
        assert len(deps.candidate_pairs) == 1


# ---------------------------------------------------------------------------
# B. WorldbuildingAgent — Instantiation
# ---------------------------------------------------------------------------


class TestWorldbuildingAgentInstantiation:
    """WorldbuildingAgent can be instantiated with/without KBAgent."""

    def test_instantiation_without_kb_agent(self) -> None:
        agent = WorldbuildingAgent(model=TestModel())
        assert isinstance(agent, WorldbuildingAgent)
        assert agent._agent is not None

    def test_instantiation_with_system_prompt(self) -> None:
        agent = WorldbuildingAgent(
            model=TestModel(),
            system_prompt="You are a worldbuilding analyst.",
        )
        assert isinstance(agent, WorldbuildingAgent)


# ---------------------------------------------------------------------------
# C. WorldbuildingAgent — run_phase2 kwargs pass-through (Task 1 core fix)
# ---------------------------------------------------------------------------


class TestRunPhase2Settings:
    """run_phase2 forwards model_settings/usage_limits to the inner run."""

    @pytest.mark.asyncio
    async def test_forwards_settings_and_limits(self) -> None:
        agent = WorldbuildingAgent(model=TestModel())
        deps = WorldbuildingDeps(candidate_pairs=[("ent-1", "ent-2")])
        expected = WorldbuildingPhase2Output(issues=[], assessment="Consistent.")
        sentinel_settings = ModelSettings(max_tokens=12_345)
        sentinel_limits = UsageLimits(request_limit=7)

        with patch.object(NarrareAgent, "run", new=AsyncMock(return_value=expected)) as mock_run:
            result = await agent.run_phase2(
                "Check consistency",
                deps,
                model=TestModel(),
                system_prompt="Phase 2 prompt.",
                model_settings=sentinel_settings,
                usage_limits=sentinel_limits,
            )

        assert result is expected
        kwargs = mock_run.call_args.kwargs
        assert kwargs["model_settings"] is sentinel_settings
        assert kwargs["usage_limits"] is sentinel_limits

    @pytest.mark.asyncio
    async def test_defaults_to_none(self) -> None:
        """Without kwargs the inner run receives None (backward compat)."""
        agent = WorldbuildingAgent(model=TestModel())
        deps = WorldbuildingDeps(candidate_pairs=[("ent-1", "ent-2")])
        expected = WorldbuildingPhase2Output(issues=[], assessment="Consistent.")

        with patch.object(NarrareAgent, "run", new=AsyncMock(return_value=expected)) as mock_run:
            result = await agent.run_phase2("Check consistency", deps, model=TestModel())

        assert result is expected
        kwargs = mock_run.call_args.kwargs
        assert kwargs["model_settings"] is None
        assert kwargs["usage_limits"] is None
