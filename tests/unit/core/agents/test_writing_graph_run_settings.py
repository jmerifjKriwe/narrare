"""Tests for WritingGraph model_settings/usage_limits pass-through.

Pins the Task-1 core pass-through of the pydantic-ai structural
follow-ups: every graph step forwards ``WritingDeps.model_settings`` /
``WritingDeps.usage_limits`` (the settings half of the
``ModelRegistry.prepare()`` triple) to the internal ``agent.run()`` call,
so API-side callers can wire the coherent triple into the graph via deps.

Test strategy (mirrors test_writing_graph_invocation.py):
- Each step is invoked directly through ``writing_graph.nodes[...]``
- ``get_model`` + the step's agent class are patched
- The run kwargs are asserted against sentinel settings/limits
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits
from pydantic_graph import StepContext

from narrare_core.agents.draft_types import DraftOutput
from narrare_core.agents.outline_types import OutlineOutput
from narrare_core.agents.review_types import ReviewOutput
from narrare_core.agents.summary_types import SummaryOutput
from narrare_core.agents.writing_graph_types import NeedsRevision
from tests.unit.core.agents.conftest import make_deps, make_state

_SENTINEL_SETTINGS: ModelSettings = ModelSettings(max_tokens=12_345)
_SENTINEL_LIMITS = UsageLimits(request_limit=7)


def _deps_with_settings(**overrides: Any) -> Any:
    """WritingDeps carrying the sentinel prepared-triple half."""
    return make_deps(
        model_settings=_SENTINEL_SETTINGS,
        usage_limits=_SENTINEL_LIMITS,
        **overrides,
    )


def _assert_run_forwards_triple(run_mock: AsyncMock) -> None:
    """Assert the agent run received the deps-carried settings/limits."""
    kwargs = run_mock.call_args.kwargs
    assert kwargs["model_settings"] is _SENTINEL_SETTINGS
    assert kwargs["usage_limits"] is _SENTINEL_LIMITS


class TestGraphStepsForwardPreparedSettings:
    """Each step forwards deps.model_settings/usage_limits to agent.run."""

    @pytest.mark.asyncio
    async def test_plan_outline_forwards_settings(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["plan_outline"]
        state = make_state()
        deps = _deps_with_settings()
        mock_output = OutlineOutput(
            chapter_title="Ch 1", scenes=["Intro"], outline_text="The outline."
        )
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.OutlineAgent") as MockAgent,
        ):
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)

        _assert_run_forwards_triple(MockAgent.return_value.run)

    @pytest.mark.asyncio
    async def test_write_draft_forwards_settings(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["write_draft"]
        state = make_state(outline="An outline.")
        deps = _deps_with_settings()
        mock_output = DraftOutput(text="A draft.")
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)

        _assert_run_forwards_triple(MockAgent.return_value.run)

    @pytest.mark.asyncio
    async def test_review_draft_forwards_settings(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["review_draft"]
        state = make_state(draft="A reviewed draft.")
        # word_target=None disables the word-count guard so the agent runs.
        deps = _deps_with_settings(word_target=None)
        mock_output = ReviewOutput(approved=True)
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.ReviewAgent") as MockAgent,
        ):
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            result = await node.call(ctx)

        assert type(result).__name__ == "Approved"
        _assert_run_forwards_triple(MockAgent.return_value.run)

    @pytest.mark.asyncio
    async def test_revise_draft_forwards_settings(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["revise_draft"]
        state = make_state(draft="Original draft.")
        deps = _deps_with_settings()
        mock_output = DraftOutput(text="Revised draft.")
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(
                state=state, deps=deps, inputs=NeedsRevision(feedback="Tighten prose.")
            )
            await node.call(ctx)

        _assert_run_forwards_triple(MockAgent.return_value.run)

    @pytest.mark.asyncio
    async def test_generate_summary_forwards_settings(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["generate_summary"]
        state = make_state(final="The final text.")
        deps = _deps_with_settings()
        mock_output = SummaryOutput(summary="A summary.")
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.ChapterSummaryAgent") as MockAgent,
        ):
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)

        _assert_run_forwards_triple(MockAgent.return_value.run)

    @pytest.mark.asyncio
    async def test_steps_default_to_none_settings(self, writing_graph: Any) -> None:
        """Without wired settings the run receives None (backward compat)."""
        node = writing_graph.nodes["write_draft"]
        state = make_state(outline="An outline.")
        deps = make_deps()  # no model_settings/usage_limits
        mock_output = DraftOutput(text="A draft.")
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)

        kwargs = MockAgent.return_value.run.call_args.kwargs
        assert kwargs["model_settings"] is None
        assert kwargs["usage_limits"] is None
