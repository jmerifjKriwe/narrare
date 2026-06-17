"""Tests for FactExtractorAgent — instantiation, deps, run.

ADR-044 — Staged Multi-Agent Consistency Pipeline.

Test strategy:
- TestModel for deterministic agent tests
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.fact_extractor_agent import FactExtractorAgent
from narrare_core.agents.fact_extractor_types import (
    FactExtractorDeps,
    FactExtractorOutput,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_model() -> TestModel:
    return TestModel()


@pytest.fixture()
def agent(test_model: TestModel) -> FactExtractorAgent:
    return FactExtractorAgent(model=test_model)


@pytest.fixture()
def deps() -> FactExtractorDeps:
    return FactExtractorDeps()


# ---------------------------------------------------------------------------
# A. Instantiation
# ---------------------------------------------------------------------------


class TestInstantiation:
    """Agent can be instantiated with TestModel."""

    def test_agent_instantiation(self, test_model: TestModel) -> None:
        agent = FactExtractorAgent(model=test_model)
        assert isinstance(agent, FactExtractorAgent)
        assert agent._agent is not None

    def test_agent_with_system_prompt(self, test_model: TestModel) -> None:
        agent = FactExtractorAgent(
            model=test_model,
            system_prompt="Extract facts from prose.",
        )
        assert isinstance(agent, FactExtractorAgent)


# ---------------------------------------------------------------------------
# B. FactExtractorDeps
# ---------------------------------------------------------------------------


class TestFactExtractorDeps:
    """FactExtractorDeps default and custom values."""

    def test_deps_default_values(self) -> None:
        deps = FactExtractorDeps()
        assert deps.language == "en"
        assert deps.genre == ""
        assert deps.chapter_texts == {}
        assert deps.kb_entity_names == []
        assert deps.kb_entity_summaries == []
        assert deps.timeline_envelopes == []

    def test_deps_custom_values(self) -> None:
        deps = FactExtractorDeps(
            chapter_texts={"ch1": "Anna walked."},
            kb_entity_names=["Anna", "The Tower"],
            timeline_envelopes=[],
            language="de",
            genre="Fantasy",
        )
        assert deps.language == "de"
        assert deps.genre == "Fantasy"
        assert "ch1" in deps.chapter_texts
        assert len(deps.kb_entity_names) == 2


# ---------------------------------------------------------------------------
# C. Agent run — TestModel returns FactExtractorOutput
# ---------------------------------------------------------------------------


class TestAgentRun:
    """Agent.run() with TestModel returns structured output."""

    @pytest.mark.asyncio
    async def test_run_returns_fact_extractor_output(
        self, agent: FactExtractorAgent, deps: FactExtractorDeps
    ) -> None:
        result = await agent.run(prompt="Extract facts from the text.", deps=deps)
        assert isinstance(result, FactExtractorOutput)
