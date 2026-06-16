"""Tests für WritingGraph + AgentRegistry Integration (ADR-016 Phase 3).

Covers:
- get_or_create_agent helper
- Graph steps use get_or_create_agent (which delegates to AgentRegistry)
- WritingDeps.agent_registry backward compatibility
- pipeline_graph.py agent_registry passthrough
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_graph import StepContext

from narrare_core.agents.draft_types import DraftOutput
from narrare_core.agents.outline_types import OutlineOutput
from narrare_core.agents.summary_types import SummaryOutput
from narrare_core.agents.writing_graph_prompts import get_or_create_agent
from narrare_core.agents.writing_graph_types import (
    WritingDeps,
    WritingState,
    WritingStatus,
    create_writing_graph,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deps(**overrides: Any) -> WritingDeps:
    defaults: dict[str, Any] = {
        "registry": AsyncMock(),
        "composer": AsyncMock(),
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


# ---------------------------------------------------------------------------
# get_or_create_agent helper
# ---------------------------------------------------------------------------


class TestGetOrCreateAgent:
    """get_or_create_agent delegates to AgentRegistry or falls back."""

    async def test_with_registry_calls_get_or_create(self) -> None:
        """When agent_registry is set, calls registry.get_or_create."""
        mock_registry = AsyncMock()
        mock_agent = MagicMock(spec=object)
        mock_registry.get_or_create = AsyncMock(return_value=mock_agent)

        deps = _make_deps(agent_registry=mock_registry)
        model = MagicMock(spec=object)

        result = await get_or_create_agent(
            deps,
            MagicMock,
            model,
            system_prompt="test prompt",
        )

        mock_registry.get_or_create.assert_called_once_with(
            MagicMock,
            model,
            system_prompt="test prompt",
        )
        assert result is mock_agent

    async def test_without_registry_creates_directly(self) -> None:
        """When agent_registry is None, creates agent directly."""

        class FakeAgent:
            def __init__(self, **kwargs: Any) -> None:
                self.kwargs = kwargs

        deps = _make_deps(agent_registry=None)
        model = MagicMock(spec=object)

        result = await get_or_create_agent(
            deps,
            FakeAgent,
            model,
            system_prompt="test",
        )

        assert isinstance(result, FakeAgent)
        assert result.kwargs["model"] is model
        assert result.kwargs["system_prompt"] == "test"

    async def test_passes_kwargs_through(self) -> None:
        """Extra kwargs are forwarded to the registry."""
        mock_registry = AsyncMock()
        mock_agent = MagicMock(spec=object)
        mock_registry.get_or_create = AsyncMock(return_value=mock_agent)

        deps = _make_deps(agent_registry=mock_registry)
        model = MagicMock(spec=object)

        await get_or_create_agent(
            deps,
            MagicMock,
            model,
            system_prompt="test",
            word_target=1000,
        )

        mock_registry.get_or_create.assert_called_once_with(
            MagicMock,
            model,
            system_prompt="test",
            word_target=1000,
        )


# ---------------------------------------------------------------------------
# WritingDeps backward compatibility
# ---------------------------------------------------------------------------


class TestWritingDepsBackwardCompat:
    """WritingDeps.agent_registry=None preserves old behavior."""

    def test_default_agent_registry_is_none(self) -> None:
        deps = WritingDeps(registry=AsyncMock(), composer=AsyncMock())
        assert deps.agent_registry is None

    def test_agent_registry_can_be_set(self) -> None:
        mock_registry = AsyncMock()
        deps = WritingDeps(registry=AsyncMock(), composer=AsyncMock(), agent_registry=mock_registry)
        assert deps.agent_registry is mock_registry


# ---------------------------------------------------------------------------
# Graph step integration — plan_outline delegates to get_or_create_agent
# ---------------------------------------------------------------------------


class TestPlanOutlineWithRegistry:
    """plan_outline step delegates to get_or_create_agent."""

    @pytest.mark.asyncio
    async def test_plan_outline_uses_get_or_create_agent(self) -> None:
        """plan_outline calls get_or_create_agent instead of direct OutlineAgent()."""
        graph = create_writing_graph()
        node = graph.nodes["plan_outline"]

        state = _make_state(chapter_id="ch-05")
        deps = _make_deps(chapter_outline="", genre="sci-fi", tone="dark")

        mock_output = OutlineOutput(
            chapter_title="The Discovery",
            scenes=["Scene 1", "Scene 2"],
            outline_text="A spaceship discovers an alien artifact.",
        )
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_output)

        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock_model",
            ),
            patch(
                "narrare_core.agents.writing_graph.get_or_create_agent",
                new_callable=AsyncMock,
                return_value=mock_agent_instance,
            ) as mock_get_or_create,
        ):
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)

            # get_or_create_agent was called with OutlineAgent type
            mock_get_or_create.assert_called_once()
            call_args = mock_get_or_create.call_args
            # Second positional arg is the model
            assert call_args[0][2] == "mock_model"

        assert state.status == WritingStatus.OUTLINED


# ---------------------------------------------------------------------------
# Graph step integration — write_draft delegates to get_or_create_agent
# ---------------------------------------------------------------------------


class TestWriteDraftWithRegistry:
    """write_draft step delegates to get_or_create_agent with word_target."""

    @pytest.mark.asyncio
    async def test_write_draft_uses_get_or_create_agent(self) -> None:
        """write_draft calls get_or_create_agent with word_target."""
        graph = create_writing_graph()
        node = graph.nodes["write_draft"]

        state = _make_state(outline="Hero enters the forest.")
        deps = _make_deps(genre="fantasy", word_target=1000)

        mock_output = DraftOutput(text="The hero walked into the forest...")
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_output)

        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock_model",
            ),
            patch(
                "narrare_core.agents.writing_graph.get_or_create_agent",
                new_callable=AsyncMock,
                return_value=mock_agent_instance,
            ) as mock_get_or_create,
        ):
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)

            mock_get_or_create.assert_called_once()
            call_kwargs = mock_get_or_create.call_args
            # word_target should be in the kwargs
            assert "word_target" in call_kwargs[1]
            assert call_kwargs[1]["word_target"] == 1000

        assert state.status == WritingStatus.DRAFTED
        assert "forest" in state.draft


# ---------------------------------------------------------------------------
# Graph step integration — generate_summary delegates to get_or_create_agent
# ---------------------------------------------------------------------------


class TestGenerateSummaryWithRegistry:
    """generate_summary step delegates to get_or_create_agent."""

    @pytest.mark.asyncio
    async def test_generate_summary_uses_get_or_create_agent(self) -> None:
        """generate_summary calls get_or_create_agent."""
        graph = create_writing_graph()
        node = graph.nodes["generate_summary"]

        state = _make_state(final="Final text", outline="Outline text")
        deps = _make_deps()

        mock_output = SummaryOutput(summary="Chapter summary text")
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run = AsyncMock(return_value=mock_output)

        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock_model",
            ),
            patch(
                "narrare_core.agents.writing_graph.get_or_create_agent",
                new_callable=AsyncMock,
                return_value=mock_agent_instance,
            ) as mock_get_or_create,
        ):
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)

            mock_get_or_create.assert_called_once()

        assert state.status == WritingStatus.SUMMARIZED
        assert state.summary == "Chapter summary text"


# ---------------------------------------------------------------------------
# Fallback — agent_registry=None still works
# ---------------------------------------------------------------------------


class TestFallbackWithoutRegistry:
    """When agent_registry is None, get_or_create_agent creates directly."""

    @pytest.mark.asyncio
    async def test_plan_outline_works_without_registry(self) -> None:
        """plan_outline works when agent_registry is None."""
        graph = create_writing_graph()
        node = graph.nodes["plan_outline"]

        state = _make_state(chapter_id="ch-05")
        deps = _make_deps(chapter_outline="", agent_registry=None)

        mock_output = OutlineOutput(outline_text="Generated outline")

        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock_model",
            ),
            patch(
                "narrare_core.agents.writing_graph.get_or_create_agent",
                new_callable=AsyncMock,
            ) as mock_get_or_create,
        ):
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_output)
            mock_get_or_create.return_value = mock_agent_instance

            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)

        assert state.status == WritingStatus.OUTLINED


# ---------------------------------------------------------------------------
# pipeline_graph.py agent_registry passthrough
# ---------------------------------------------------------------------------


class TestPipelineGraphPassthrough:
    """pipeline_graph.py accepts and passes agent_registry to WritingDeps."""

    def test_stream_signature_accepts_agent_registry(self) -> None:
        from narrare_core.writing.pipeline_graph import stream_via_writing_graph

        sig = inspect.signature(stream_via_writing_graph)
        assert "agent_registry" in sig.parameters

    def test_run_with_persistence_signature_accepts_agent_registry(self) -> None:
        from narrare_core.writing.pipeline_graph import run_with_persistence

        sig = inspect.signature(run_with_persistence)
        assert "agent_registry" in sig.parameters

    def test_agent_registry_default_is_none_stream(self) -> None:
        from narrare_core.writing.pipeline_graph import stream_via_writing_graph

        sig = inspect.signature(stream_via_writing_graph)
        param = sig.parameters["agent_registry"]
        assert param.default is None

    def test_agent_registry_default_is_none_persistence(self) -> None:
        from narrare_core.writing.pipeline_graph import run_with_persistence

        sig = inspect.signature(run_with_persistence)
        param = sig.parameters["agent_registry"]
        assert param.default is None

    def test_stream_signature_requires_composer(self) -> None:
        """CR-AUFG-02-07: composer is a required parameter (no default)."""
        from narrare_core.writing.pipeline_graph import stream_via_writing_graph

        sig = inspect.signature(stream_via_writing_graph)
        param = sig.parameters["composer"]
        assert param.default is inspect.Parameter.empty

    def test_run_with_persistence_signature_requires_composer(self) -> None:
        """CR-AUFG-02-07: composer is a required parameter (no default)."""
        from narrare_core.writing.pipeline_graph import run_with_persistence

        sig = inspect.signature(run_with_persistence)
        param = sig.parameters["composer"]
        assert param.default is inspect.Parameter.empty
