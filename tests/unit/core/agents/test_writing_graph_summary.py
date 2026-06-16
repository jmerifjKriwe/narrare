"""Tests für WritingGraph generate_summary Step.

Node-Tests via StepContext + graph.nodes[...].call() mit gemocktem ChapterSummaryAgent.
Keine echten LLM-Calls (RULE-01).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_graph import End, StepContext

from narrare_core.agents.summary_types import SummaryOutput
from narrare_core.agents.writing_graph_types import (
    WritingDeps,
    WritingState,
    WritingStatus,
    create_writing_graph,
)
from narrare_core.prompts.composer import ComposedPrompt


@pytest.fixture()
def writing_graph():  # type: ignore[no-untyped-def]
    return create_writing_graph()


def _mock_composer() -> AsyncMock:
    """Build a PromptComposer mock whose build() returns a ComposedPrompt."""
    mock = AsyncMock()
    mock.build = AsyncMock(
        return_value=ComposedPrompt(system="Composed system prompt.", user="Composed user prompt.")
    )
    return mock


def _make_deps(**overrides: Any) -> WritingDeps:
    defaults: dict[str, Any] = {
        "registry": AsyncMock(),
        "composer": _mock_composer(),
        "genre": "fantasy",
        "tone": "balanced",
        "word_target": 1000,
    }
    defaults.update(overrides)
    return WritingDeps(**defaults)


def _make_state(**overrides: Any) -> WritingState:
    defaults: dict[str, Any] = {"chapter_id": "ch-01"}
    defaults.update(overrides)
    return WritingState(**defaults)


class MockStore:
    def __init__(self) -> None:
        self.saves: list[tuple[str, object]] = []

    async def save(self, run_id: str, state: object) -> None:
        self.saves.append((run_id, state))

    async def load(self, run_id: str) -> object | None:
        return None

    async def delete(self, run_id: str) -> None:
        pass


class TestGenerateSummary:
    """generate_summary step — mit ChapterSummaryAgent Mock."""

    @pytest.mark.asyncio
    async def test_generate_summary_with_draft(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["generate_summary"]
        state = _make_state(
            draft="The hero fought bravely against the dark lord and won.",
            outline="The Final Battle",
        )
        deps = _make_deps(genre="fantasy", writing_language="en")
        mock_output = SummaryOutput(
            summary="The hero defeats the dark lord.", key_points=["Hero fights", "Victory"]
        )
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock_model",
            ),
            patch("narrare_core.agents.writing_graph.ChapterSummaryAgent") as MockAgent,
        ):
            mock_inst = AsyncMock()
            mock_inst.run = AsyncMock(return_value=mock_output)
            MockAgent.return_value = mock_inst
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)
        assert ctx.state.summary == "The hero defeats the dark lord."
        assert ctx.state.status == WritingStatus.SUMMARIZED

    @pytest.mark.asyncio
    async def test_generate_summary_uses_final_when_available(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["generate_summary"]
        state = _make_state(draft="Draft.", final="Final polished.", outline="Outline")
        deps = _make_deps(genre="fantasy", writing_language="en")
        mock_output = SummaryOutput(summary="Summary of final.", key_points=["Final summarized"])
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock_model",
            ),
            patch("narrare_core.agents.writing_graph.ChapterSummaryAgent") as MockAgent,
        ):
            mock_inst = AsyncMock()
            mock_inst.run = AsyncMock(return_value=mock_output)
            MockAgent.return_value = mock_inst
            ctx = StepContext(state=state, deps=deps, inputs=None)
            result = await node.call(ctx)
        assert isinstance(result, End)
        assert ctx.state.summary == "Summary of final."

    @pytest.mark.asyncio
    async def test_generate_summary_empty_content(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["generate_summary"]
        state = _make_state(draft="", final="  ")
        deps = _make_deps(genre="fantasy")
        ctx = StepContext(state=state, deps=deps, inputs=None)
        result = await node.call(ctx)
        assert isinstance(result, End)
        assert ctx.state.summary == ""
        assert ctx.state.status == WritingStatus.SUMMARIZED

    @pytest.mark.asyncio
    async def test_generate_summary_calls_chapter_summary_agent(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["generate_summary"]
        state = _make_state(draft="Some content.", outline="Chapter 5: Revelation")
        deps = _make_deps(genre="mystery", writing_language="de")
        mock_output = SummaryOutput(summary="Eine Zusammenfassung.", key_points=["Punkt 1"])
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock_model",
            ),
            patch("narrare_core.agents.writing_graph.ChapterSummaryAgent") as MockAgent,
        ):
            mock_inst = AsyncMock()
            mock_inst.run = AsyncMock(return_value=mock_output)
            MockAgent.return_value = mock_inst
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)
        mock_inst.run.assert_called_once()
        prompt_arg = mock_inst.run.call_args[1]["prompt"]
        # CR-AUFG-02-07: prompt comes from PromptComposer (not inline fallback)
        assert isinstance(prompt_arg, str)

    @pytest.mark.asyncio
    async def test_generate_summary_saves_state(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["generate_summary"]
        store = MockStore()
        state = _make_state(draft="Final content.")
        deps = _make_deps(store=store, run_id="run-summary")
        mock_output = SummaryOutput(summary="A test summary.", key_points=["Key point 1"])
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock_model",
            ),
            patch("narrare_core.agents.writing_graph.ChapterSummaryAgent") as MockAgent,
        ):
            mock_inst = AsyncMock()
            mock_inst.run = AsyncMock(return_value=mock_output)
            MockAgent.return_value = mock_inst
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)
        assert len(store.saves) == 1
        assert store.saves[0][0] == "run-summary"
