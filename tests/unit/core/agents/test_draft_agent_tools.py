"""Tests für DraftAgent — Tool und End-to-End (E2E).

Testet get_kb_context-Tool und vollständige agent.run()-Durchläufe
mit TestModel (keine echten LLM-Calls, RULE-01 eingehalten).
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.draft_agent import DraftAgent
from narrare_core.agents.draft_types import DraftDeps, DraftOutput

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_model() -> TestModel:
    return TestModel()


@pytest.fixture()
def agent(test_model: TestModel) -> DraftAgent:
    return DraftAgent(model=test_model)


@pytest.fixture()
def deps() -> DraftDeps:
    return DraftDeps()


@pytest.fixture()
def run_context(test_model: TestModel) -> RunContext[DraftDeps]:
    return RunContext[DraftDeps](
        deps=DraftDeps(),
        model=test_model,
        usage=RunUsage(),
    )


# ---------------------------------------------------------------------------
# D. Tool
# ---------------------------------------------------------------------------


class TestTool:
    """D. Tool — get_kb_context (2 Tests)."""

    @pytest.mark.asyncio
    async def test_get_kb_context_returns_string(
        self,
        agent: DraftAgent,
        run_context: RunContext[DraftDeps],
    ) -> None:
        """KB-Tool gibt immer einen String zurück."""
        result = await agent.get_kb_context(
            run_context,
            entity_names=["character1"],
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_kb_context_without_assembler(
        self,
        agent: DraftAgent,
        run_context: RunContext[DraftDeps],
    ) -> None:
        """Ohne ContextAssembler sinnvoller Fallback."""
        result = await agent.get_kb_context(
            run_context,
            entity_names=["hero", "village"],
        )
        assert result == "No context assembler available."


# ---------------------------------------------------------------------------
# E. End-to-End
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """E. End-to-End — agent.run() mit TestModel (2 Tests)."""

    @pytest.mark.asyncio
    async def test_run_with_testmodel_returns_draft_output(
        self,
        agent: DraftAgent,
        deps: DraftDeps,
    ) -> None:
        """Vollständiger agent.run() liefert DraftOutput."""
        result = await agent.run(prompt="Test prompt", deps=deps)
        assert isinstance(result, DraftOutput)
        assert isinstance(result.text, str)
        assert result.word_count >= 0

    @pytest.mark.asyncio
    async def test_run_passes_deps(
        self,
        agent: DraftAgent,
    ) -> None:
        """Deps werden durchgereicht — kein Fehler."""
        result = await agent.run(prompt="Test", deps=DraftDeps())
        assert isinstance(result, DraftOutput)
