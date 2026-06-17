"""Tests für OutlineAgent — Instantiation, Output Function, Basic Behavior.

Test-Strategie:
- TestModel für deterministische Agent-Tests
- Output Function wird direkt via ``_process_outline`` getestet
- Keine echten LLM-Calls (RULE-01b)
"""

from __future__ import annotations

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.outline_agent import OutlineAgent, OutlineDeps
from narrare_core.agents.outline_types import OutlineOutput

# ---------------------------------------------------------------------------
# A. OutlineDeps
# ---------------------------------------------------------------------------


class TestOutlineDeps:
    """OutlineDeps erzeugt und konfiguriert korrekt."""

    def test_defaults(self) -> None:
        deps = OutlineDeps()
        assert deps.genre == ""
        assert deps.tone == "balanced"
        assert deps.language == "en"

    def test_custom_values(self) -> None:
        deps = OutlineDeps(genre="Fantasy", tone="dark", language="de")
        assert deps.genre == "Fantasy"
        assert deps.tone == "dark"
        assert deps.language == "de"


# ---------------------------------------------------------------------------
# B. OutlineOutput
# ---------------------------------------------------------------------------


class TestOutlineOutput:
    """OutlineOutput validiert korrekt."""

    def test_defaults(self) -> None:
        output = OutlineOutput()
        assert output.chapter_title == ""
        assert output.scenes == []
        assert output.outline_text == ""

    def test_with_values(self) -> None:
        output = OutlineOutput(
            chapter_title="The Dark Forest",
            scenes=["Scene 1: Entry", "Scene 2: Discovery"],
            outline_text="Full outline text",
        )
        assert output.chapter_title == "The Dark Forest"
        assert len(output.scenes) == 2
        assert output.outline_text == "Full outline text"


# ---------------------------------------------------------------------------
# C. OutlineAgent — Instantiation
# ---------------------------------------------------------------------------


class TestOutlineAgent:
    """OutlineAgent instantiiert und executed korrekt."""

    def test_can_be_instantiated(self) -> None:
        model = TestModel()
        agent = OutlineAgent(model=model)
        assert isinstance(agent, OutlineAgent)
        assert agent._agent is not None

    def test_can_be_instantiated_with_test_model(self) -> None:
        """Mit TestModel (kein echter LLM-Call)."""
        model = TestModel()
        agent = OutlineAgent(model=model)
        assert isinstance(agent, OutlineAgent)
        assert agent._agent is not None


# ---------------------------------------------------------------------------
# D. Output Function — _process_outline
# ---------------------------------------------------------------------------


class TestProcessOutline:
    """Output Function wird korrekt ausgeführt."""

    @pytest.fixture()
    def run_context(self) -> RunContext[OutlineDeps]:
        return RunContext[OutlineDeps](
            deps=OutlineDeps(),
            model=TestModel(),
            usage=RunUsage(),
        )

    @pytest.mark.asyncio
    async def test_process_outline_with_scenes(
        self,
        run_context: RunContext[OutlineDeps],
    ) -> None:
        """Scenes + chapter_title → korrektes OutlineOutput."""
        result = await OutlineAgent(model=TestModel())._process_outline(
            run_context,
            scenes=["Intro", "Conflict", "Resolution"],
            chapter_title="The Final Battle",
        )
        assert result.chapter_title == "The Final Battle"
        assert len(result.scenes) == 3
        assert "Intro" in result.outline_text
        assert "Conflict" in result.outline_text

    @pytest.mark.asyncio
    async def test_process_outline_partial_streaming(
        self,
        run_context: RunContext[OutlineDeps],
    ) -> None:
        """partial_output → leeres OutlineOutput."""
        run_context.partial_output = True
        result = await OutlineAgent(model=TestModel())._process_outline(
            run_context,
            scenes=["Partial scene"],
            chapter_title="Partial",
        )
        assert result.chapter_title == ""  # no processing during streaming
        assert result.scenes == []

    @pytest.mark.asyncio
    async def test_process_outline_empty(
        self,
        run_context: RunContext[OutlineDeps],
    ) -> None:
        """Keine scenes/chapter_title → leeres OutlineOutput."""
        result = await OutlineAgent(model=TestModel())._process_outline(
            run_context,
            scenes=None,
            chapter_title=None,
        )
        assert result.chapter_title == ""
        assert result.scenes == []
        assert result.outline_text == ""

    @pytest.mark.asyncio
    async def test_process_outline_outline_text_generation(
        self,
        run_context: RunContext[OutlineDeps],
    ) -> None:
        """outline_text = scenes joined by double newline."""
        result = await OutlineAgent(model=TestModel())._process_outline(
            run_context,
            scenes=["Scene one.", "Scene two.", "Scene three."],
        )
        assert result.outline_text == "Scene one.\n\nScene two.\n\nScene three."
