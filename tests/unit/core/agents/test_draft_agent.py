"""Tests für DraftAgent — Instantiation, Output Function, Basic Behavior.

Test-Strategie:
- ``TestModel`` für deterministische Agent-Tests
- Output Function wird direkt via ``_process_draft_output`` getestet
- Keine echten LLM-Calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.test import TestModel

from narrare_core.agents.draft_agent import DraftAgent, DraftDeps
from narrare_core.agents.draft_types import DraftConfig, DraftOutput

# ---------------------------------------------------------------------------
# Shared fixtures
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
# A. Instantiation & Basic Behavior
# ---------------------------------------------------------------------------


class TestInstantiation:
    """A. Instantiation & Basic Behavior (4 Tests)."""

    @pytest.mark.asyncio
    async def test_can_be_instantiated(self, agent: DraftAgent) -> None:
        """DraftAgent kann mit TestModel instanziiert werden."""
        assert isinstance(agent, DraftAgent)
        assert agent._agent is not None

    def test_draft_output_creation(self) -> None:
        """DraftOutput kann manuell erstellt werden."""
        output = DraftOutput(text="Draft content")
        assert output.text == "Draft content"
        assert output.word_count == 0

    def test_draft_config_creation(self) -> None:
        """DraftConfig mit verschiedenen Modi erstellbar."""
        assert DraftConfig(mode="full_draft").mode == "full_draft"
        assert DraftConfig(mode="scene_by_scene").mode == "scene_by_scene"

    @pytest.mark.asyncio
    async def test_output_type_is_draft_output(
        self,
        agent: DraftAgent,
        deps: DraftDeps,
    ) -> None:
        """Agent.run() liefert DraftOutput (nicht str)."""
        result = await agent.run(prompt="Test", deps=deps)
        assert isinstance(result, DraftOutput)
        assert isinstance(result.text, str)


# ---------------------------------------------------------------------------
# B. Output Function
# ---------------------------------------------------------------------------


class TestOutputFunction:
    """B. Output Function — _process_draft_output (4 Tests)."""

    @pytest.mark.asyncio
    async def test_process_draft_output_strips_artifacts(
        self,
        agent: DraftAgent,
        run_context: RunContext[DraftDeps],
    ) -> None:
        """Entfernt 'Here is your chapter draft:' und **Note:**."""
        result = await agent._process_draft_output(
            run_context,
            text="Here is your chapter draft:\n\nThe wind howled.",
            title="Chapter 1",
        )
        assert "Here is your chapter draft:" not in result.text
        assert "The wind howled." in result.text
        assert result.title == "Chapter 1"

    @pytest.mark.asyncio
    async def test_process_draft_output_normalises_markdown(
        self,
        agent: DraftAgent,
        run_context: RunContext[DraftDeps],
    ) -> None:
        """4+ blank lines → 2."""
        result = await agent._process_draft_output(
            run_context,
            text="Para one.\n\n\n\n\nPara two.",
        )
        assert "\n\n\n" not in result.text

    @pytest.mark.asyncio
    async def test_process_draft_output_counts_words(
        self,
        agent: DraftAgent,
        run_context: RunContext[DraftDeps],
    ) -> None:
        """word_count korrekt."""
        text = "The quick brown fox jumps over the lazy dog"
        result = await agent._process_draft_output(run_context, text=text)
        assert result.word_count == len(text.split())

    @pytest.mark.asyncio
    async def test_process_draft_output_partial_streaming(
        self,
        agent: DraftAgent,
        run_context: RunContext[DraftDeps],
    ) -> None:
        """partial_output → keine Vollverarbeitung."""
        run_context.partial_output = True
        result = await agent._process_draft_output(
            run_context,
            text="Here is your chapter draft:\n\nPartial.",
        )
        assert "Here is your chapter draft:" in result.text  # nicht gestripped
        assert result.word_count == 0  # nicht berechnet


# ---------------------------------------------------------------------------
# C. Validator
# ---------------------------------------------------------------------------


class TestValidator:
    """C. Validator — Qualitäts-Check via ModelRetry (3 Tests)."""

    @pytest.mark.asyncio
    async def test_validate_draft_rejects_short_draft(
        self,
        run_context: RunContext[DraftDeps],
    ) -> None:
        """word_count < target*0.5 → ModelRetry."""
        agent = DraftAgent(model=TestModel(), word_target=100)
        short = " ".join(f"w{i}" for i in range(40))
        with pytest.raises(ModelRetry, match="Output too short"):
            await agent._process_draft_output(run_context, text=short)

    @pytest.mark.asyncio
    async def test_validate_draft_accepts_long_enough_draft(
        self,
        run_context: RunContext[DraftDeps],
    ) -> None:
        """word_count >= target*0.5 → OK."""
        agent = DraftAgent(model=TestModel(), word_target=100)
        long = " ".join(f"w{i}" for i in range(60))
        result = await agent._process_draft_output(run_context, text=long)
        assert result.word_count >= 50

    @pytest.mark.asyncio
    async def test_validate_draft_skips_partial_output(
        self,
        run_context: RunContext[DraftDeps],
    ) -> None:
        """partial_output → kein Validator-Lauf."""
        agent = DraftAgent(model=TestModel(), word_target=100)
        run_context.partial_output = True
        short = " ".join(f"w{i}" for i in range(10))
        result = await agent._process_draft_output(run_context, text=short)
        assert isinstance(result, DraftOutput)
        assert result.text == short
