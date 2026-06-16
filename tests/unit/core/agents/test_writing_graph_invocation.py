"""Tests für WritingGraph invocation pipeline integration.

Testet:
- Jeder Graph-Step ruft _run_invocation_pipeline auf, wenn pipeline gesetzt.
- Backward compatibility: pipeline=None ist ein No-Op.
- user_id/project_id werden korrekt an den InvocationContext übergeben.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_graph import StepContext

from narrare_core.agents.draft_types import DraftOutput
from narrare_core.agents.outline_types import OutlineOutput
from narrare_core.agents.review_types import ReviewOutput
from narrare_core.agents.writing_graph_types import Approved, NeedsRevision, WritingStatus
from tests.unit.core.agents.conftest import SpyPipeline, make_deps, make_state

# ---------------------------------------------------------------------------
# A. Backward compatibility — pipeline=None means no-op
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    """Ohne pipeline = kein Fehler, bestehendes Verhalten bleibt erhalten."""

    @pytest.mark.asyncio
    async def test_plan_outline_without_pipeline_succeeds(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["plan_outline"]
        state = make_state()
        deps = make_deps(pipeline=None, chapter_outline="Pre-existing outline.")
        ctx = StepContext(state=state, deps=deps, inputs=None)
        await node.call(ctx)
        assert state.outline == "Pre-existing outline."
        assert state.status == WritingStatus.OUTLINED

    @pytest.mark.asyncio
    async def test_write_draft_without_pipeline_succeeds(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["write_draft"]
        state = make_state(outline="An outline.")
        deps = make_deps(pipeline=None)
        mock_output = DraftOutput(text="Draft without pipeline.")
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)
        assert state.draft == "Draft without pipeline."
        assert state.status == WritingStatus.DRAFTED


# ---------------------------------------------------------------------------
# B. Pipeline integration — each step calls prepare+finalize
# ---------------------------------------------------------------------------


class TestPlanOutlineWithPipeline:
    @pytest.mark.asyncio
    async def test_calls_pipeline_prepare_and_finalize(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["plan_outline"]
        pipeline = SpyPipeline()
        state = make_state()
        deps = make_deps(pipeline=pipeline, chapter_outline="")
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
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)
        assert len(pipeline.prepare_calls) == 1
        assert len(pipeline.finalize_calls) == 1
        assert pipeline.prepare_calls[0].feature_id == "writing_graph_plan_outline"
        assert pipeline.prepare_calls[0].user_id == "user-42"
        assert pipeline.prepare_calls[0].project_id == "novel-1"

    @pytest.mark.asyncio
    async def test_skips_pipeline_when_outline_given(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["plan_outline"]
        pipeline = SpyPipeline()
        deps = make_deps(pipeline=pipeline, chapter_outline="Has outline already.")
        ctx = StepContext(state=make_state(), deps=deps, inputs=None)
        await node.call(ctx)
        assert len(pipeline.prepare_calls) == 0


class TestWriteDraftWithPipeline:
    @pytest.mark.asyncio
    async def test_calls_pipeline_prepare_and_finalize(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["write_draft"]
        pipeline = SpyPipeline()
        state = make_state(outline="Outline.")
        deps = make_deps(pipeline=pipeline)
        mock_output = DraftOutput(text="Pipeline draft.")
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)
        assert len(pipeline.prepare_calls) == 1
        assert len(pipeline.finalize_calls) == 1
        assert pipeline.prepare_calls[0].feature_id == "writing_graph_write_draft"
        assert pipeline.prepare_calls[0].intent == "write"

    @pytest.mark.asyncio
    async def test_invocation_context_has_correct_fields(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["write_draft"]
        pipeline = SpyPipeline()
        state = make_state(novel_id="novel-99", outline="Outline.")
        deps = make_deps(pipeline=pipeline, user_id="user-88")
        mock_output = DraftOutput(text="Context check.")
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)
        call_ctx = pipeline.prepare_calls[0]
        assert call_ctx.user_id == "user-88"
        assert call_ctx.project_id == "novel-99"


class TestReviewDraftWithPipeline:
    @pytest.mark.asyncio
    async def test_calls_pipeline_when_reviewing(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["review_draft"]
        pipeline = SpyPipeline()
        state = make_state(draft=" ".join(["word"] * 800), attempts=0)
        deps = make_deps(pipeline=pipeline, word_target=1000)
        mock_output = ReviewOutput(approved=True, feedback="Great.", quality_score=8)
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.ReviewAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            result = await node.call(ctx)
        assert isinstance(result, Approved)
        assert len(pipeline.prepare_calls) == 1
        assert pipeline.prepare_calls[0].feature_id == "writing_graph_review_draft"

    @pytest.mark.asyncio
    async def test_skips_pipeline_for_word_count_guard(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["review_draft"]
        pipeline = SpyPipeline()
        state = make_state(draft=". ".join(["short"] * 5), attempts=0)
        deps = make_deps(pipeline=pipeline, word_target=1000)
        ctx = StepContext(state=state, deps=deps, inputs=None)
        result = await node.call(ctx)
        assert isinstance(result, NeedsRevision)
        assert len(pipeline.prepare_calls) == 0

    @pytest.mark.asyncio
    async def test_skips_pipeline_for_max_attempts(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["review_draft"]
        pipeline = SpyPipeline()
        state = make_state(draft="short", attempts=3)
        deps = make_deps(pipeline=pipeline, word_target=1000)
        ctx = StepContext(state=state, deps=deps, inputs=None)
        result = await node.call(ctx)
        assert isinstance(result, Approved)
        assert len(pipeline.prepare_calls) == 0


class TestReviseDraftWithPipeline:
    @pytest.mark.asyncio
    async def test_calls_pipeline_prepare_and_finalize(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["revise_draft"]
        pipeline = SpyPipeline()
        state = make_state(draft="Original.", attempts=1)
        deps = make_deps(pipeline=pipeline, genre="fantasy", tone="dramatic")
        mock_output = DraftOutput(text="Revised.")
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=NeedsRevision(feedback="Fix it."))
            await node.call(ctx)
        assert len(pipeline.prepare_calls) == 1
        assert pipeline.prepare_calls[0].feature_id == "writing_graph_revise_draft"


class TestGenerateSummaryWithPipeline:
    @pytest.mark.asyncio
    async def test_calls_pipeline_prepare_and_finalize(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["generate_summary"]
        pipeline = SpyPipeline()
        state = make_state(draft="A complete chapter.")
        deps = make_deps(pipeline=pipeline)
        mock_output = AsyncMock()
        mock_output.summary = "A summary."
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.ChapterSummaryAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_output)
            ctx = StepContext(state=state, deps=deps, inputs=None)
            await node.call(ctx)
        assert len(pipeline.prepare_calls) == 1
        assert pipeline.prepare_calls[0].feature_id == "writing_graph_generate_summary"
        assert state.status == WritingStatus.SUMMARIZED

    @pytest.mark.asyncio
    async def test_skips_pipeline_when_no_content(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["generate_summary"]
        pipeline = SpyPipeline()
        state = make_state(draft="", final="")
        deps = make_deps(pipeline=pipeline)
        ctx = StepContext(state=state, deps=deps, inputs=None)
        await node.call(ctx)
        assert len(pipeline.prepare_calls) == 0
