"""Tests for the ``{{series_history}}`` prompt variable wiring (Spec 2, Task 7).

Validates the Core-side plumbing that lets the Backend pass a pre-assembled
series-history string through the writing pipeline into the governed
``{{series_history}}`` prompt slot:

1. ``series_history`` is a registered SYSTEM_VAR (RULE-22 governance).
2. :class:`WritingContext` carries the field and exposes it via
   ``to_prompt_variables()``.
3. :class:`WritingContextAssembler.assemble` threads the kwarg into the
   assembled context.
4. :func:`assemble_writing_context` (Stage 2) forwards the kwarg to the
   assembler.
5. :meth:`WritingPipeline.generate` accepts and forwards ``series_history``.
6. ``_build_prompt_context`` places ``series_history`` into
   :class:`PromptContext.extra` so the variable engine can resolve
   ``{{series_history}}``.

The Backend fetch (BandSummary data → :class:`SeriesHistoryTier`) is covered
by the Backend provider tests; this module is the pure Core contract.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare_core.llm.result import StreamChunk
from narrare_core.prompts.variable_registry import (
    SYSTEM_VARS,
    get_variable_classification,
    is_registered_variable,
)
from narrare_core.writing._enums import GenerationMode
from narrare_core.writing._stages import assemble_writing_context
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline

# ---------------------------------------------------------------------------
# 1. Variable governance (RULE-22)
# ---------------------------------------------------------------------------


class TestSeriesHistoryVariableGovernance:
    """``{{series_history}}`` must be in the governed taxonomy."""

    def test_registered_in_system_vars(self) -> None:
        assert "series_history" in SYSTEM_VARS

    def test_is_registered_variable(self) -> None:
        assert is_registered_variable("series_history")

    def test_has_classification_metadata(self) -> None:
        cls = get_variable_classification("series_history")
        assert cls is not None
        assert cls.name == "series_history"


# ---------------------------------------------------------------------------
# 2. WritingContext carries the field
# ---------------------------------------------------------------------------


class TestWritingContextField:
    """WritingContext exposes ``series_history`` (default empty)."""

    def test_default_is_empty_string(self) -> None:
        ctx = WritingContext()
        assert ctx.series_history == ""

    def test_field_is_settable(self) -> None:
        ctx = WritingContext(series_history="Previously in this series:\n\nBand 1 — …")
        assert ctx.series_history.startswith("Previously in this series")

    def test_to_prompt_variables_includes_series_history(self) -> None:
        ctx = WritingContext(series_history="some history")
        variables = ctx.to_prompt_variables()
        assert variables["series_history"] == "some history"

    def test_to_prompt_variables_defaults_empty(self) -> None:
        variables = WritingContext().to_prompt_variables()
        assert variables["series_history"] == ""


# ---------------------------------------------------------------------------
# 3. WritingContextAssembler threads the kwarg
# ---------------------------------------------------------------------------


class TestAssemblerThreading:
    """``WritingContextAssembler.assemble(series_history=...)`` → context."""

    @pytest.mark.asyncio
    async def test_assemble_threads_series_history(self) -> None:
        assembler = WritingContextAssembler()

        ctx = await assembler.assemble(series_history="PREVIOUSLY…")

        assert ctx.series_history == "PREVIOUSLY…"

    @pytest.mark.asyncio
    async def test_assemble_defaults_series_history_empty(self) -> None:
        assembler = WritingContextAssembler()

        ctx = await assembler.assemble()

        assert ctx.series_history == ""


# ---------------------------------------------------------------------------
# 4. Stage-2 helper forwards the kwarg
# ---------------------------------------------------------------------------


def _request() -> GenerationRequest:
    return GenerationRequest(
        chapter_id=uuid4(),
        project_id=uuid4(),
        user_id=uuid4(),
        mode=GenerationMode.FULL_DRAFT,
    )


def _make_pipeline_with_mock_assembler() -> tuple[WritingPipeline, Any]:
    assembler = MagicMock(spec=WritingContextAssembler)
    assembler.assemble = AsyncMock(return_value=WritingContext())
    pipeline = WritingPipeline(
        registry=MagicMock(spec=["stream", "run"]),
        composer=MagicMock(spec=["build"]),
        context_assembler=assembler,
        draft_processor=MagicMock(spec=["process"]),
    )
    return pipeline, assembler


class TestStageForwardsSeriesHistory:
    """``assemble_writing_context`` forwards ``series_history`` verbatim."""

    @pytest.mark.asyncio
    async def test_forwards_series_history_to_assembler(self) -> None:
        pipeline, assembler = _make_pipeline_with_mock_assembler()

        await assemble_writing_context(
            pipeline,
            _request(),
            voice_profile_consumer=None,
            chapter_content="",
            chapter_frontmatter="",
            chapter_outline="",
            recent_chapters=None,
            kb_entities=None,
            entity_connections=None,
            kb_relationships="",
            project_title="",
            genre="",
            user_preferences="",
            avoidance_patterns="",
            series_history="Band 1 context…",
        )

        kwargs = assembler.assemble.call_args.kwargs
        assert kwargs["series_history"] == "Band 1 context…"

    @pytest.mark.asyncio
    async def test_series_history_defaults_empty(self) -> None:
        pipeline, assembler = _make_pipeline_with_mock_assembler()

        await assemble_writing_context(
            pipeline,
            _request(),
            voice_profile_consumer=None,
            chapter_content="",
            chapter_frontmatter="",
            chapter_outline="",
            recent_chapters=None,
            kb_entities=None,
            entity_connections=None,
            kb_relationships="",
            project_title="",
            genre="",
            user_preferences="",
            avoidance_patterns="",
        )

        kwargs = assembler.assemble.call_args.kwargs
        assert kwargs["series_history"] == ""


# ---------------------------------------------------------------------------
# 5. WritingPipeline.generate accepts the kwarg
# ---------------------------------------------------------------------------


class TestPipelineGenerateAcceptsKwarg:
    """``WritingPipeline.generate`` accepts ``series_history`` and forwards it."""

    @pytest.mark.asyncio
    async def test_generate_forwards_series_history_to_stage(self) -> None:
        pipeline, assembler = _make_pipeline_with_mock_assembler()
        request = _request()

        # Patch the FULL_DRAFT graph streamer so the generator completes
        # cleanly (Stage-2 assembly runs before the dispatch regardless).
        async def _fake_graph(*a: Any, **kw: Any) -> Any:
            yield StreamChunk(text="done", is_final=True)

        with patch(
            "narrare_core.writing.pipeline_graph.stream_via_writing_graph",
            side_effect=lambda *a, **kw: _fake_graph(a, kw),
        ):
            async for _chunk in pipeline.generate(
                request,
                config=MagicMock(spec=["model_id", "provider_name"]),
                series_history="Some series history.",
            ):
                pass

        kwargs = assembler.assemble.call_args.kwargs
        assert kwargs["series_history"] == "Some series history."


# ---------------------------------------------------------------------------
# 6. _build_prompt_context places it into PromptContext.extra
# ---------------------------------------------------------------------------


class TestBuildPromptContextExtra:
    """The prompt context carries ``series_history`` for the variable engine."""

    def test_series_history_in_extra(self) -> None:
        pipeline, _ = _make_pipeline_with_mock_assembler()
        ctx = WritingContext(series_history="Previously…")

        prompt_ctx = pipeline._build_prompt_context(  # pyright: ignore[reportPrivateUsage]
            _request(),
            ctx,
        )

        assert prompt_ctx.extra["series_history"] == "Previously…"

    def test_series_history_resolves_via_as_variables(self) -> None:
        pipeline, _ = _make_pipeline_with_mock_assembler()
        ctx = WritingContext(series_history="Previously…")

        prompt_ctx = pipeline._build_prompt_context(  # pyright: ignore[reportPrivateUsage]
            _request(),
            ctx,
        )

        assert prompt_ctx.as_variables()["series_history"] == "Previously…"
