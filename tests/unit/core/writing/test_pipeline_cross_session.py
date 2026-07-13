"""Tests for cross_session_context passthrough in the writing pipeline.

Verifies the memory-layer plumbing that lets cross-session mem0 memories
reach writing prompts (mirrors the entity_connections / user_preferences
passthrough pattern):

1. ``generate()`` forwards ``cross_session_context`` to the assembler.
2. Omitting it forwards an empty string (backward compatible).
3. ``_build_prompt_context()`` surfaces it on the ``PromptContext`` so the
   composer can inject ``{{cross_session_context}}`` into the template.

Extracted from ``test_pipeline.py`` for RULE-04 compliance (file-size limit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.prompts.context import PromptContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=2000,
        streams=True,
    )


def _request() -> GenerationRequest:
    return GenerationRequest(
        chapter_id=uuid4(),
        project_id=uuid4(),
        user_id=uuid4(),
        mode=GenerationMode.FULL_DRAFT,
    )


def _default_context() -> WritingContext:
    return WritingContext(
        chapter_content="Previous content.",
        project_title="Test Novel",
        genre="fantasy",
        language="en",
        tone="balanced",
    )


async def _collect(iterator: AsyncIterator[StreamChunk]) -> list[StreamChunk]:
    chunks: list[StreamChunk] = []
    async for chunk in iterator:
        chunks.append(chunk)
    return chunks


@pytest.fixture()
def pipeline() -> WritingPipeline:
    """WritingPipeline with a mock assembler returning a default context."""
    asm = MagicMock(spec=WritingContextAssembler)
    asm.assemble = AsyncMock(return_value=_default_context())
    reg = MagicMock(spec=["stream", "run", "get_model"])
    comp = MagicMock(spec=PromptComposer)
    comp.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="user"))
    proc = MagicMock(spec=DraftProcessor)
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return WritingPipeline(
        registry=reg,
        composer=comp,
        context_assembler=asm,
        draft_processor=proc,
    )


@pytest.fixture()
def mock_assembler(pipeline: WritingPipeline) -> Any:
    """Expose the pipeline's mock assembler for call inspection."""
    return pipeline._context_assembler  # pyright: ignore[reportPrivateUsage]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCrossSessionContextPassthrough:
    """cross_session_context flows generate() → assembler → PromptContext."""

    @pytest.mark.asyncio
    async def test_generate_passes_cross_session_context_to_assembler(
        self,
        pipeline: WritingPipeline,
        mock_assembler: Any,
    ) -> None:
        """cross_session_context kwarg is forwarded to context_assembler.assemble()."""
        with patch(
            "narrare_core.writing.pipeline_graph.stream_via_writing_graph",
        ) as mock_graph_stream:

            async def fake_gen(*a: Any, **kw: Any) -> AsyncIterator[StreamChunk]:
                yield StreamChunk(text="done", is_final=True)

            mock_graph_stream.side_effect = lambda *a, **kw: fake_gen(a, kw)

            memory = "- Author dislikes cliffhangers."
            await _collect(
                pipeline.generate(
                    _request(),
                    config=_config(),
                    cross_session_context=memory,
                ),
            )

        assemble_call = mock_assembler.assemble.call_args
        assert assemble_call.kwargs.get("cross_session_context") == memory

    @pytest.mark.asyncio
    async def test_generate_without_cross_session_context_defaults_empty(
        self,
        pipeline: WritingPipeline,
        mock_assembler: Any,
    ) -> None:
        """Omitting cross_session_context forwards an empty string (backward compat)."""
        with patch(
            "narrare_core.writing.pipeline_graph.stream_via_writing_graph",
        ) as mock_graph_stream:

            async def fake_gen(*a: Any, **kw: Any) -> AsyncIterator[StreamChunk]:
                yield StreamChunk(text="done", is_final=True)

            mock_graph_stream.side_effect = lambda *a, **kw: fake_gen(a, kw)

            await _collect(
                pipeline.generate(_request(), config=_config()),
            )

        assemble_call = mock_assembler.assemble.call_args
        assert assemble_call.kwargs.get("cross_session_context") == ""

    @pytest.mark.asyncio
    async def test_build_prompt_context_includes_cross_session_context(
        self,
        pipeline: WritingPipeline,
    ) -> None:
        """_build_prompt_context surfaces cross_session_context for the composer."""
        ctx = WritingContext(cross_session_context="- Author likes dialogue.")
        prompt_ctx: PromptContext = pipeline._build_prompt_context(  # pyright: ignore[reportPrivateUsage]
            _request(),
            ctx,
        )

        assert prompt_ctx.cross_session_context == "- Author likes dialogue."

    @pytest.mark.asyncio
    async def test_build_prompt_context_cross_session_context_empty_by_default(
        self,
        pipeline: WritingPipeline,
    ) -> None:
        """_build_prompt_context defaults cross_session_context to empty."""
        ctx = WritingContext()
        prompt_ctx: PromptContext = pipeline._build_prompt_context(  # pyright: ignore[reportPrivateUsage]
            _request(),
            ctx,
        )

        assert prompt_ctx.cross_session_context == ""
