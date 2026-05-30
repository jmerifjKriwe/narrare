"""Tests for pipeline CO_AUTHOR mode dispatch.

Tests that ``WritingPipeline.generate()`` dispatches correctly for
``GenerationMode.CO_AUTHOR``, forwarding parameters to ``stream_coauthor``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from narrare_core.llm.result import StreamChunk
from tests.unit.core.writing._coauthor_test_helpers import (
    _collect,
    _config,
    _make_chunks,
    _request,
    _usage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.writing.pipeline import WritingPipeline


class TestPipelineDispatchCoAuthor:
    """Test that pipeline.generate() dispatches correctly for CO_AUTHOR."""

    @pytest.mark.asyncio
    async def test_co_author_dispatches_to_coauthor_module(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """CO_AUTHOR mode streams via stream_coauthor."""
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_make_chunks("Better text."),
        )
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )

        with patch(
            "narrare_core.writing.pipeline_coauthor.stream_coauthor",
        ) as mock_stream_coauthor:

            async def fake_stream(*a: Any, **kw: Any) -> AsyncIterator[StreamChunk]:
                yield StreamChunk(text="From co-author.")
                yield StreamChunk(text="", is_final=True, usage=_usage())

            mock_stream_coauthor.side_effect = fake_stream

            chunks = await _collect(
                pipeline.generate(
                    _request(),
                    config=_config(),
                    selection_text="Original.",
                    co_author_focus=["dialogue", "description"],
                ),
            )

            # First chunk is context metadata (CR-07)
            assert len(chunks) >= 2
            texts = [c.text for c in chunks]
            assert "From co-author." in texts

    @pytest.mark.asyncio
    async def test_forwards_co_author_focus(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """co_author_focus parameter forwarded to stream_coauthor."""
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_make_chunks("Revised."),
        )
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )

        with patch(
            "narrare_core.writing.pipeline_coauthor.stream_coauthor",
        ) as mock_stream_coauthor:

            async def fake_stream(*a: Any, **kw: Any) -> AsyncIterator[StreamChunk]:
                yield StreamChunk(text="Done.", is_final=True, usage=_usage())

            mock_stream_coauthor.side_effect = fake_stream

            await _collect(
                pipeline.generate(
                    _request(),
                    config=_config(),
                    selection_text="Original.",
                    co_author_focus=["sentence"],
                ),
            )

            # Verify focus= was forwarded
            call_kwargs = mock_stream_coauthor.call_args.kwargs
            assert call_kwargs["focus"] == ["sentence"]

    @pytest.mark.asyncio
    async def test_forwards_selection_context(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """selection_text, context_before, context_after forwarded."""
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_make_chunks("Revised."),
        )
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )

        with patch(
            "narrare_core.writing.pipeline_coauthor.stream_coauthor",
        ) as mock_stream_coauthor:

            async def fake_stream(*a: Any, **kw: Any) -> AsyncIterator[StreamChunk]:
                yield StreamChunk(text="Done.", is_final=True, usage=_usage())

            mock_stream_coauthor.side_effect = fake_stream

            await _collect(
                pipeline.generate(
                    _request(),
                    config=_config(),
                    selection_text="Selected.",
                    context_before="Before. ",
                    context_after=" After.",
                ),
            )

            kwargs = mock_stream_coauthor.call_args.kwargs
            assert kwargs["selection_text"] == "Selected."
            assert kwargs["context_before"] == "Before. "
            assert kwargs["context_after"] == " After."

    @pytest.mark.asyncio
    async def test_default_co_author_focus_is_none(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """When co_author_focus not provided, streams with None (handled by fn)."""
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_make_chunks("Revised."),
        )
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )

        with patch(
            "narrare_core.writing.pipeline_coauthor.stream_coauthor",
        ) as mock_stream_coauthor:

            async def fake_stream(*a: Any, **kw: Any) -> AsyncIterator[StreamChunk]:
                yield StreamChunk(text="Done.", is_final=True, usage=_usage())

            mock_stream_coauthor.side_effect = fake_stream

            await _collect(
                pipeline.generate(
                    _request(),
                    config=_config(),
                    selection_text="Selected.",
                ),
            )

            kwargs = mock_stream_coauthor.call_args.kwargs
            assert kwargs["focus"] is None
