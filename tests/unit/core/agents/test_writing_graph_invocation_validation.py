"""Tests für WritingGraph invocation pipeline — Validation & Integration.

Testet:
- FailingPipeline (ValidationError Propagation)
- InvocationContext Feld-Korrektheit (all steps)
- pipeline_graph / pipeline integration
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
from narrare_core.ai_invocation.pipeline import InvocationPipeline
from narrare_core.shared.errors import InvocationValidationError

from .conftest import FailingPipeline, SpyPipeline, make_deps, make_state

# ---------------------------------------------------------------------------
# C. Pipeline Validation Error Propagation
# ---------------------------------------------------------------------------


class TestValidationErrorPropagation:
    """Wenn pipeline.prepare() FAIL returned, muss der Graph-Step den Fehler
    propagieren (raise), damit der graph-übergreifende Error-Handler ihn
    abfangen kann."""

    @pytest.mark.asyncio
    async def test_plan_outline_propagates_validation_error(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["plan_outline"]
        pipeline = FailingPipeline()
        deps = make_deps(pipeline=pipeline, chapter_outline="")
        ctx = _make_step_ctx(state=make_state(), deps=deps)
        with pytest.raises(InvocationValidationError) as exc_info:
            await node.call(ctx)
        assert "missing_var" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_write_draft_propagates_validation_error(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["write_draft"]
        pipeline = FailingPipeline()
        deps = make_deps(pipeline=pipeline)
        state = make_state(outline="Outline.")
        ctx = _make_step_ctx(state=state, deps=deps)
        with pytest.raises(InvocationValidationError) as exc_info:
            await node.call(ctx)
        assert "missing_var" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_review_draft_propagates_validation_error(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["review_draft"]
        pipeline = FailingPipeline()
        state = make_state(draft=" ".join(["word"] * 800), attempts=0)
        deps = make_deps(pipeline=pipeline, word_target=1000)
        ctx = _make_step_ctx(state=state, deps=deps)
        with pytest.raises(InvocationValidationError) as exc_info:
            await node.call(ctx)
        assert "missing_var" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_revise_draft_propagates_validation_error(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["revise_draft"]
        pipeline = FailingPipeline()
        state = make_state(draft="Original.", attempts=1)
        deps = make_deps(pipeline=pipeline)
        ctx = _make_step_ctx(state=state, deps=deps, inputs=_fake_needs_revision())
        with pytest.raises(InvocationValidationError) as exc_info:
            await node.call(ctx)
        assert "missing_var" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_summary_propagates_validation_error(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["generate_summary"]
        pipeline = FailingPipeline()
        state = make_state(draft="A chapter.")
        deps = make_deps(pipeline=pipeline)
        ctx = _make_step_ctx(state=state, deps=deps)
        with pytest.raises(InvocationValidationError) as exc_info:
            await node.call(ctx)
        assert "missing_var" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_plan_outline_raises_when_failing_pipeline(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["plan_outline"]
        pipeline = FailingPipeline()
        deps = make_deps(pipeline=pipeline, chapter_outline="")
        ctx = _make_step_ctx(state=make_state(), deps=deps)
        with pytest.raises(InvocationValidationError):
            await node.call(ctx)


# ---------------------------------------------------------------------------
# D. WritingDeps carries pipeline; pipeline_graph signatures
# ---------------------------------------------------------------------------


class TestWritingDepsCarriesPipeline:
    def test_writing_deps_accepts_pipeline(self) -> None:
        deps = WritingDeps(  # type: ignore[call-arg]
            registry=AsyncMock(),
            composer=AsyncMock(),
            genre="fantasy",
            tone="balanced",
            word_target=1000,
            invocation_pipeline=InvocationPipeline(),
            user_id="u-1",
        )
        assert deps.invocation_pipeline is not None  # type: ignore[attr-defined]

    def test_writing_deps_default_pipeline_is_none(self) -> None:
        deps = WritingDeps(  # type: ignore[call-arg]
            registry=AsyncMock(),
            composer=AsyncMock(),
            genre="fantasy",
            tone="balanced",
            word_target=1000,
            user_id="u-1",
        )
        assert deps.invocation_pipeline is None  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# E. Invocation context fields per step
# ---------------------------------------------------------------------------


class TestInvocationContextFields:
    """Detaillierte Prüfung der InvocationContext-Felder für jeden Step."""

    @pytest.mark.asyncio
    async def test_plan_outline_context_fields(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["plan_outline"]
        pipeline = SpyPipeline()
        deps = make_deps(pipeline=pipeline, user_id="u-field", chapter_outline="")
        state = make_state(novel_id="n-field")
        mock_outline = AsyncMock()
        mock_outline.chapter_title = "T"
        mock_outline.scenes = []
        mock_outline.outline_text = "O"
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.OutlineAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_outline)
            ctx = _make_step_ctx(state=state, deps=deps)
            await node.call(ctx)
        c = pipeline.prepare_calls[0]
        assert c.feature_id == "writing_graph_plan_outline"
        assert c.user_id == "u-field"
        assert c.project_id == "n-field"
        assert c.intent is not None

    @pytest.mark.asyncio
    async def test_write_draft_context_fields(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["write_draft"]
        pipeline = SpyPipeline()
        deps = make_deps(pipeline=pipeline, user_id="wu")
        state = make_state(novel_id="wp", outline="O.")
        mock_draft = AsyncMock()
        mock_draft.text = "D"
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_draft)
            ctx = _make_step_ctx(state=state, deps=deps)
            await node.call(ctx)
        c = pipeline.prepare_calls[0]
        assert c.feature_id == "writing_graph_write_draft"
        assert c.user_id == "wu"
        assert c.project_id == "wp"

    @pytest.mark.asyncio
    async def test_review_draft_context_fields(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["review_draft"]
        pipeline = SpyPipeline()
        deps = make_deps(pipeline=pipeline, user_id="ru")
        state = make_state(novel_id="rp", draft=" ".join(["w"] * 800), attempts=0)
        mock_review = AsyncMock()
        mock_review.approved = True
        mock_review.feedback = "ok"
        mock_review.quality_score = 7
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.ReviewAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_review)
            ctx = _make_step_ctx(state=state, deps=deps)
            await node.call(ctx)
        c = pipeline.prepare_calls[0]
        assert c.feature_id == "writing_graph_review_draft"
        assert c.user_id == "ru"
        assert c.project_id == "rp"

    @pytest.mark.asyncio
    async def test_revise_draft_context_fields(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["revise_draft"]
        pipeline = SpyPipeline()
        deps = make_deps(pipeline=pipeline, user_id="vru")
        state = make_state(novel_id="vrp", draft="Draft.", attempts=1)
        mock_draft = AsyncMock()
        mock_draft.text = "Revised."
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.DraftAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_draft)
            ctx = _make_step_ctx(state=state, deps=deps, inputs=_fake_needs_revision())
            await node.call(ctx)
        c = pipeline.prepare_calls[0]
        assert c.feature_id == "writing_graph_revise_draft"
        assert c.user_id == "vru"
        assert c.project_id == "vrp"

    @pytest.mark.asyncio
    async def test_summary_context_fields(self, writing_graph: Any) -> None:
        node = writing_graph.nodes["generate_summary"]
        pipeline = SpyPipeline()
        deps = make_deps(pipeline=pipeline, user_id="su")
        state = make_state(novel_id="sp", draft="Chapter.")
        mock_summary = AsyncMock()
        mock_summary.summary = "S."
        with (
            patch(
                "narrare_core.agents.writing_graph.get_model",
                new_callable=AsyncMock,
                return_value="mock",
            ),
            patch("narrare_core.agents.writing_graph.ChapterSummaryAgent") as MockAgent,
        ):
            MockAgent.return_value = AsyncMock()
            MockAgent.return_value.run = AsyncMock(return_value=mock_summary)
            ctx = _make_step_ctx(state=state, deps=deps)
            await node.call(ctx)
        c = pipeline.prepare_calls[0]
        assert c.feature_id == "writing_graph_generate_summary"
        assert c.user_id == "su"
        assert c.project_id == "sp"


# ---------------------------------------------------------------------------
# F. pipeline_graph and pipeline integration (signatures)
# ---------------------------------------------------------------------------


class TestPipelineGraphIntegration:
    """Contract tests: stream_via_writing_graph / run_with_persistence
    accept invocation_pipeline parameter."""

    def test_stream_via_writing_graph_accepts_invocation_pipeline_param(self) -> None:
        import inspect

        from narrare_core.writing.pipeline_graph import stream_via_writing_graph

        sig = inspect.signature(stream_via_writing_graph)
        assert "invocation_pipeline" in sig.parameters
        param = sig.parameters["invocation_pipeline"]
        assert param.default is None

    def test_run_with_persistence_accepts_invocation_pipeline_param(self) -> None:
        import inspect

        from narrare_core.writing.pipeline_graph import run_with_persistence

        sig = inspect.signature(run_with_persistence)
        assert "invocation_pipeline" in sig.parameters
        param = sig.parameters["invocation_pipeline"]
        assert param.default is None


class TestPipelineIntegration:
    def test_writing_pipeline_accepts_invocation_pipeline(self) -> None:
        from unittest.mock import AsyncMock

        from narrare_core.writing.pipeline import WritingPipeline

        pipeline = InvocationPipeline()
        wp = WritingPipeline(
            registry=AsyncMock(),
            composer=AsyncMock(),
            context_assembler=AsyncMock(),
            draft_processor=AsyncMock(),
            invocation_pipeline=pipeline,
        )
        assert wp._invocation_pipeline is pipeline

    def test_writing_pipeline_default_pipeline_is_none(self) -> None:
        from unittest.mock import AsyncMock

        from narrare_core.writing.pipeline import WritingPipeline

        wp = WritingPipeline(
            registry=AsyncMock(),
            composer=AsyncMock(),
            context_assembler=AsyncMock(),
            draft_processor=AsyncMock(),
        )
        assert wp._invocation_pipeline is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step_ctx(
    state: WritingState,
    deps: WritingDeps,
    inputs: Any = None,
) -> Any:
    """Create a StepContext (pydantic-graph internal)."""
    from pydantic_graph import StepContext

    return StepContext(state=state, deps=deps, inputs=inputs)


def _fake_needs_revision() -> Any:
    from narrare_core.agents.writing_graph_types import NeedsRevision

    return NeedsRevision(feedback="Please revise.")
