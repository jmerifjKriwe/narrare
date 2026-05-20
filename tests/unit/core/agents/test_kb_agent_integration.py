"""Integrationstests — KBAgent-Tools in DraftAgent.

Test-Strategie:
- TestModel für deterministische Tests
- DraftAgent mit/ohne KBAgent-Konstruktor-Argument
- Keine echten LLM-Calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from narrare_core.agents.draft_agent import DraftAgent, DraftDeps
from narrare_core.agents.draft_types import DraftOutput
from narrare_core.agents.kb_agent import KBAgent


@pytest.fixture()
def test_model() -> TestModel:
    return TestModel()


class TestIntegration:
    """DraftAgent mit/ohne KBAgent (3 Tests)."""

    @pytest.mark.asyncio
    async def test_draft_agent_accepts_kb_agent(
        self,
        test_model: TestModel,
    ) -> None:
        """DraftAgent(model=m, kb_agent=kb_agent) funktioniert."""
        kb_agent = KBAgent(model=test_model)
        draft = DraftAgent(model=test_model, kb_agent=kb_agent)
        assert isinstance(draft, DraftAgent)
        assert draft._kb_agent is kb_agent

        result = await draft.run(prompt="Write a chapter", deps=DraftDeps())
        assert isinstance(result, DraftOutput)

    @pytest.mark.asyncio
    async def test_draft_agent_without_kb_agent_still_works(
        self,
        test_model: TestModel,
    ) -> None:
        """DraftAgent(model=m) ohne KBAgent funktioniert weiterhin."""
        draft = DraftAgent(model=test_model)
        assert isinstance(draft, DraftAgent)
        assert draft._kb_agent is None

        result = await draft.run(prompt="Write a chapter", deps=DraftDeps())
        assert isinstance(result, DraftOutput)

    @pytest.mark.asyncio
    async def test_draft_agent_with_kb_agent_runs_with_deps(
        self,
        test_model: TestModel,
    ) -> None:
        """DraftAgent + KBAgent + vollständige Deps (kein word_target,
        da TestModel zu kurzen Output liefert)."""
        kb_agent = KBAgent(model=test_model)
        draft = DraftAgent(model=test_model, kb_agent=kb_agent)
        result = await draft.run(prompt="Test", deps=DraftDeps())
        assert isinstance(result, DraftOutput)
        assert result.word_count >= 0
