"""Tests for agents/worldbuilding_agent.py — Instantiation and Output Functions.

Test-Strategie:
- TestModel for deterministic agent tests
- Output Functions tested directly via _process_phase1 / _process_phase2
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from narrare_core.agents.worldbuilding_agent import WorldbuildingAgent
from narrare_core.agents.worldbuilding_types import WorldbuildingDeps

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
