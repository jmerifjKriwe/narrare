"""Tests für WritingGraph — Graph-Build und Node-Tests.

Test-Strategie:
- Node-Tests via StepContext + graph.nodes[...].call()
- LLM-Mocking via unittest.mock (DraftAgent, _get_model)
- Keine echten LLM-Calls (RULE-01)
- Coverage-Ziel: writing_graph.py > 85%
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_graph import StepContext

from narrare_core.agents.draft_types import DraftOutput
from narrare_core.agents.writing_graph import create_writing_graph
from narrare_core.agents.writing_graph_types import (
    Approved,
    NeedsRevision,
    WritingDeps,
    WritingState,
    WritingStatus,
)


@pytest.fixture()
def writing_graph():  # type: ignore[no-untyped-def]
    """Build den Writing-Graph einmal pro Test."""
    return create_writing_graph()


def _make_deps(**overrides: Any) -> WritingDeps:
    defaults: dict[str, Any] = {
        "registry": AsyncMock(),
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


# A. Graph Build + Structure


class TestGraphBuild:
    def test_graph_builds_without_error(self) -> None:
        graph = create_writing_graph()
        assert graph is not None

    def test_graph_renders_mermaid(self, writing_graph: Any) -> None:
        mermaid = writing_graph.render()
        assert isinstance(mermaid, str)
        assert "stateDiagram" in mermaid

    def test_graph_has_correct_node_count(self, writing_graph: Any) -> None:
        expected = {"plan_outline", "write_draft", "review_draft", "revise_draft", "finalize"}
        actual = set(writing_graph.nodes.keys())
        assert expected.issubset(actual)


# B. Node-Tests — Pure Logic


class TestPlanOutline:
    @pytest.mark.asyncio
    async def test_plan_outline_sets_status(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["plan_outline"]
        state = _make_state()
        deps = _make_deps(chapter_outline="Hero enters the forest.")
        ctx = StepContext(state=state, deps=deps, inputs=None)
        await node.call(ctx)
        assert state.outline == "Hero enters the forest."
        assert state.status == WritingStatus.OUTLINED

    @pytest.mark.asyncio
    async def test_plan_outline_generates_default_outline(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["plan_outline"]
        state = _make_state(chapter_id="ch-42")
        deps = _make_deps(chapter_outline="")
        ctx = StepContext(state=state, deps=deps, inputs=None)
        await node.call(ctx)
        assert "ch-42" in state.outline
        assert state.status == WritingStatus.OUTLINED


class TestReviewDraft:
    @pytest.mark.asyncio
    async def test_review_returns_approved(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["review_draft"]
        draft = " ".join(["word"] * 800)
        state = _make_state(draft=draft, attempts=0)
        deps = _make_deps(word_target=1000)
        ctx = StepContext(state=state, deps=deps, inputs=None)
        result = await node.call(ctx)
        assert isinstance(result, Approved)

    @pytest.mark.asyncio
    async def test_review_returns_needs_revision(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["review_draft"]
        draft = " ".join(["word"] * 200)
        state = _make_state(draft=draft, attempts=0)
        deps = _make_deps(word_target=1000)
        ctx = StepContext(state=state, deps=deps, inputs=None)
        result = await node.call(ctx)
        assert isinstance(result, NeedsRevision)
        assert "short" in result.feedback.lower()

    @pytest.mark.asyncio
    async def test_max_revisions_forces_approval(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["review_draft"]
        state = _make_state(draft="short", attempts=3)
        deps = _make_deps(word_target=1000)
        ctx = StepContext(state=state, deps=deps, inputs=None)
        result = await node.call(ctx)
        assert isinstance(result, Approved)


class TestFinalize:
    @pytest.mark.asyncio
    async def test_finalize_sets_final(self, writing_graph: Any) -> None:
        from pydantic_graph import End

        node = writing_graph.nodes["finalize"]
        state = _make_state(draft="Draft text.", revision="Revised text.")
        deps = _make_deps()
        ctx = StepContext(state=state, deps=deps, inputs=Approved())
        result = await node.call(ctx)
        assert isinstance(result, End)
        assert state.final == "Revised text."
        assert state.status == WritingStatus.COMPLETED


# C. Node-Tests — Mit DraftAgent Mock


class TestWriteDraft:
    @pytest.mark.asyncio
    async def test_write_draft_updates_state(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["write_draft"]
        state = _make_state(outline="Hero journey outline.")
        deps = _make_deps(genre="fantasy", tone="dramatic")
        mock_output = DraftOutput(text="A brave hero sets out on a journey...")

        with (
            patch(
                "narrare_core.agents.writing_graph._get_model",
                new_callable=AsyncMock,
                return_value="mock_model",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            mock_instance = AsyncMock()
            mock_instance.run = AsyncMock(return_value=mock_output)
            MockAgent.return_value = mock_instance
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)

        assert state.draft == "A brave hero sets out on a journey..."
        assert state.status == WritingStatus.DRAFTED


class TestReviseDraft:
    @pytest.mark.asyncio
    async def test_revise_draft_updates_state(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["revise_draft"]
        state = _make_state(draft="Original draft.", attempts=1)
        deps = _make_deps(genre="fantasy", tone="dramatic")
        mock_output = DraftOutput(text="Revised and improved draft.")
        revision_signal = NeedsRevision(feedback="Expand the ending.")

        with (
            patch(
                "narrare_core.agents.writing_graph._get_model",
                new_callable=AsyncMock,
                return_value="mock_model",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            mock_instance = AsyncMock()
            mock_instance.run = AsyncMock(return_value=mock_output)
            MockAgent.return_value = mock_instance
            ctx = StepContext(state=state, deps=deps, inputs=revision_signal)
            await node.call(ctx)

        assert state.feedback == "Expand the ending."
        assert state.revision == "Revised and improved draft."
        assert state.draft == "Revised and improved draft."
        assert state.status == WritingStatus.REVISED


# D. State Persistence — _save_state


class MockStore:
    """Simple mock for GraphStateStore to verify save calls."""

    def __init__(self) -> None:
        self.saves: list[tuple[str, object]] = []

    async def save(self, run_id: str, state: object) -> None:
        self.saves.append((run_id, state))

    async def load(self, run_id: str) -> object | None:
        return None

    async def delete(self, run_id: str) -> None:
        pass


class TestStatePersistence:
    """_save_state wird korrekt aufgerufen — oder nicht, wenn store=None."""

    @pytest.mark.asyncio
    async def test_plan_outline_saves_state_with_store(self, writing_graph: Any) -> None:
        """plan_outline ruft _save_state auf wenn store gesetzt ist."""
        node = writing_graph.nodes["plan_outline"]
        store = MockStore()
        state = _make_state()
        deps = _make_deps(chapter_outline="Outline.", store=store, run_id="run-1")
        ctx = StepContext(state=state, deps=deps, inputs=None)
        await node.call(ctx)
        assert len(store.saves) == 1
        assert store.saves[0][0] == "run-1"
        assert store.saves[0][1] is state

    @pytest.mark.asyncio
    async def test_plan_outline_does_not_crash_without_store(self, writing_graph: Any) -> None:
        """plan_outline darf nicht crashen wenn store=None."""
        node = writing_graph.nodes["plan_outline"]
        state = _make_state()
        deps = _make_deps(chapter_outline="Outline.", store=None, run_id="")
        ctx = StepContext(state=state, deps=deps, inputs=None)
        await node.call(ctx)  # should not raise

    @pytest.mark.asyncio
    async def test_review_draft_saves_on_approved(self, writing_graph: Any) -> None:
        """review_draft ruft _save_state bei Approved auf."""
        node = writing_graph.nodes["review_draft"]
        store = MockStore()
        state = _make_state(draft=" ".join(["word"] * 800), attempts=0)
        deps = _make_deps(word_target=1000, store=store, run_id="run-1")
        ctx = StepContext(state=state, deps=deps, inputs=None)
        result = await node.call(ctx)
        assert isinstance(result, Approved)
        assert len(store.saves) == 1

    @pytest.mark.asyncio
    async def test_review_draft_saves_on_needs_revision(self, writing_graph: Any) -> None:
        """review_draft ruft _save_state bei NeedsRevision auf."""
        node = writing_graph.nodes["review_draft"]
        store = MockStore()
        state = _make_state(draft=" ".join(["word"] * 200), attempts=0)
        deps = _make_deps(word_target=1000, store=store, run_id="run-1")
        ctx = StepContext(state=state, deps=deps, inputs=None)
        result = await node.call(ctx)
        assert isinstance(result, NeedsRevision)
        assert len(store.saves) == 1

    @pytest.mark.asyncio
    async def test_review_draft_saves_on_max_attempts(self, writing_graph: Any) -> None:
        """review_draft ruft _save_state bei max revisions."""
        node = writing_graph.nodes["review_draft"]
        store = MockStore()
        state = _make_state(draft="short", attempts=3)
        deps = _make_deps(word_target=1000, store=store, run_id="run-1")
        ctx = StepContext(state=state, deps=deps, inputs=None)
        result = await node.call(ctx)
        assert isinstance(result, Approved)
        assert len(store.saves) == 1

    @pytest.mark.asyncio
    async def test_finalize_saves_state(self, writing_graph: Any) -> None:
        """finalize ruft _save_state auf."""
        from pydantic_graph import End

        node = writing_graph.nodes["finalize"]
        store = MockStore()
        state = _make_state(draft="Final text.")
        deps = _make_deps(store=store, run_id="run-42")
        ctx = StepContext(state=state, deps=deps, inputs=Approved())
        result = await node.call(ctx)
        assert isinstance(result, End)
        assert len(store.saves) == 1
        assert store.saves[0][0] == "run-42"
