"""Tests for ExtractionAgent — instantiation, deps, basic behavior.

Test strategy:
- TestModel for deterministic agent tests
- Validator tested directly via _validate_output (test_extraction_validation.py)
- No real LLM calls (RULE-01b)
"""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.extraction_agent import ExtractionAgent, ExtractionDeps
from narrare_core.agents.extraction_types import ExtractionOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_model() -> TestModel:
    return TestModel()


@pytest.fixture()
def agent(test_model: TestModel) -> ExtractionAgent:
    return ExtractionAgent(model=test_model)


@pytest.fixture()
def deps() -> ExtractionDeps:
    return ExtractionDeps()


# ---------------------------------------------------------------------------
# A. Instantiation
# ---------------------------------------------------------------------------


class TestInstantiation:
    """Agent can be instantiated with and without KBAgent."""

    def test_agent_instantiation_without_kb_agent(self, test_model: TestModel) -> None:
        agent = ExtractionAgent(model=test_model)
        assert isinstance(agent, ExtractionAgent)
        assert agent._agent is not None

    def test_agent_instantiation_with_kb_agent(self, test_model: TestModel) -> None:
        """When KBAgent is provided, capabilities include ToolSearch + Toolset."""
        from narrare_core.agents.kb_agent import KBAgent

        kb_agent = KBAgent(model=test_model)
        agent = ExtractionAgent(model=test_model, kb_agent=kb_agent)
        assert isinstance(agent, ExtractionAgent)
        assert agent._agent is not None

    def test_retries_forwarded_to_base_agent(
        self, test_model: TestModel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ExtractionAgent forwards ``retries`` to the NarrareAgent base constructor."""
        import narrare_core.agents.base as base_module

        class CapturingAgent:
            calls: ClassVar[list[dict[str, Any]]] = []

            def __init__(self, **kwargs: Any) -> None:
                self.calls.append(kwargs)

            def output_validator(self, validator: Any) -> Any:
                return validator

        monkeypatch.setattr(base_module, "Agent", CapturingAgent)
        before = len(CapturingAgent.calls)

        ExtractionAgent(model=test_model, retries=4)

        assert len(CapturingAgent.calls) == before + 1
        assert CapturingAgent.calls[-1]["retries"] == 4


# ---------------------------------------------------------------------------
# B. ExtractionDeps
# ---------------------------------------------------------------------------


class TestExtractionDeps:
    """ExtractionDeps default and custom values."""

    def test_deps_default_values(self) -> None:
        deps = ExtractionDeps()
        assert deps.language == "en"
        assert deps.genre == ""
        assert deps.novel_id == ""
        assert deps.existing_entity_names == []
        assert deps.chapter_title == ""

    def test_deps_custom_values(self) -> None:
        deps = ExtractionDeps(
            language="de",
            genre="Fantasy",
            novel_id="novel-42",
            existing_entity_names=["Anna", "The Tower"],
            chapter_title="Chapter 5: The Crossing",
        )
        assert deps.language == "de"
        assert deps.genre == "Fantasy"
        assert deps.novel_id == "novel-42"
        assert deps.existing_entity_names == ["Anna", "The Tower"]
        assert deps.chapter_title == "Chapter 5: The Crossing"

    def test_deps_existing_entity_names_default(self) -> None:
        """existing_entity_names defaults to empty list."""
        deps = ExtractionDeps()
        assert deps.existing_entity_names == []
        assert isinstance(deps.existing_entity_names, list)


# ---------------------------------------------------------------------------
# C. Agent run — TestModel returns ExtractionOutput
# ---------------------------------------------------------------------------


class TestAgentRun:
    """Agent.run() with TestModel returns structured output."""

    @pytest.mark.asyncio
    async def test_run_returns_extraction_output(
        self, agent: ExtractionAgent, deps: ExtractionDeps
    ) -> None:
        result = await agent.run(prompt="Anna walked through the dark forest.", deps=deps)
        assert isinstance(result, ExtractionOutput)
