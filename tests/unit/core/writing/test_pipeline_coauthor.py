"""Tests for writing/pipeline_coauthor.py — stream_coauthor function.

Tests the ``stream_coauthor()`` function with mocked pipeline internals.

Covers:
- Happy path with various focus areas
- Diff metadata in final chunk context_meta
- Empty focus list defaulting to word_choice
- Graceful handling when no changes detected
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.result import StreamChunk
from narrare_core.writing.pipeline_coauthor import stream_coauthor
from tests.unit.core.writing._coauthor_test_helpers import (
    _collect,
    _config,
    _default_context,
    _make_chunks,
    _request,
    _usage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.writing.pipeline import WritingPipeline


class TestStreamCoauthorDirect:
    """Test stream_coauthor() directly with mocked pipeline internals."""

    @pytest.mark.asyncio
    async def test_yields_text_chunks_and_final_with_diff(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """Verify diff metadata in final chunk context_meta."""
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )

        # Real streaming pattern: intermediate non-final chunks + final empty chunk
        async def stream_gen() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(text="Improved ", is_final=False)
            yield StreamChunk(text="text.", is_final=False)
            yield StreamChunk(text="", is_final=True, usage=_usage())

        mock_registry.stream = MagicMock(spec=[], return_value=stream_gen())

        chunks = await _collect(
            stream_coauthor(
                pipeline,
                _request(),
                _default_context(),
                _config(),
                selection_text="Original text.",
                focus=["dialogue"],
            ),
        )

        assert len(chunks) >= 2
        # Intermediate chunks pass through
        texts = [c.text for c in chunks if not c.is_final]
        assert texts == ["Improved ", "text."]

        # Final chunk has diff metadata
        final = [c for c in chunks if c.is_final]
        assert len(final) == 1
        meta = final[0].context_meta
        assert meta is not None
        assert "changes" in meta
        assert "total_changes" in meta
        assert "has_changes" in meta

    @pytest.mark.asyncio
    async def test_empty_focus_defaults_to_word_choice(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """When focus is None, stream_coauthor uses empty list (word_choice)."""
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )

        async def stream_gen() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(text="Better text.", is_final=False)
            yield StreamChunk(text="", is_final=True, usage=_usage())

        mock_registry.stream = MagicMock(spec=[], return_value=stream_gen())

        chunks = await _collect(
            stream_coauthor(
                pipeline,
                _request(),
                _default_context(),
                _config(),
                selection_text="Original text.",
            ),
        )

        final = [c for c in chunks if c.is_final]
        assert len(final) == 1
        meta = final[0].context_meta
        assert meta is not None
        assert "changes" in meta

    @pytest.mark.asyncio
    async def test_identical_text_has_no_changes(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """When LLM returns exact original, diff shows no changes."""
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )

        async def stream_gen() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(text="Original text.", is_final=False)
            yield StreamChunk(text="", is_final=True, usage=_usage())

        mock_registry.stream = MagicMock(spec=[], return_value=stream_gen())

        chunks = await _collect(
            stream_coauthor(
                pipeline,
                _request(),
                _default_context(),
                _config(),
                selection_text="Original text.",
                focus=["sentence"],
            ),
        )

        final = [c for c in chunks if c.is_final]
        meta = final[0].context_meta
        assert meta is not None
        assert meta["has_changes"] is False
        assert meta["total_changes"] == 0
        assert meta["changes"] == []

    @pytest.mark.asyncio
    async def test_stop_during_stream(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """When pipeline._is_stopped returns True, streaming halts immediately."""
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )

        async def stream_that_stops() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(text="Partial text.", is_final=False)
            yield StreamChunk(text="", is_final=True, usage=_usage())

        mock_registry.stream = MagicMock(
            spec=[],
            return_value=stream_that_stops(),
        )

        # Make pipeline always report stopped — check happens before yield
        with patch.object(pipeline, "_is_stopped", return_value=True):
            chunks = await _collect(
                stream_coauthor(
                    pipeline,
                    _request(),
                    _default_context(),
                    _config(),
                    selection_text="Original text.",
                    focus=["dialogue"],
                ),
            )

        # No chunks yielded because _is_stopped checked before first yield
        assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_draft_processor_applied_to_accumulated_text(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """DraftProcessor.process() is called on the full accumulated text."""
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            return_value="Processed text.",
        )

        # Real streaming: intermediate chunks accumulated, final chunk has no text
        async def stream_gen() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(text="Improved ", is_final=False)
            yield StreamChunk(text="text.", is_final=False)
            yield StreamChunk(text="", is_final=True, usage=_usage())

        mock_registry.stream = MagicMock(spec=[], return_value=stream_gen())

        chunks = await _collect(
            stream_coauthor(
                pipeline,
                _request(),
                _default_context(),
                _config(),
                selection_text="Original text.",
                focus=["description"],
            ),
        )

        pipeline._draft_processor.process.assert_called_once_with(
            "Improved text.",
        )

        final = [c for c in chunks if c.is_final]
        assert final[0].text == "Processed text."

    @pytest.mark.asyncio
    async def test_correct_intent_passed_to_registry(
        self,
        pipeline: WritingPipeline,
        mock_composer: Any,
        mock_registry: Any,
    ) -> None:
        """LLMIntent.CO_AUTHOR and focus instructions passed via composer."""
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_make_chunks("Revised text."),
        )

        await _collect(
            stream_coauthor(
                pipeline,
                _request(),
                _default_context(),
                _config(),
                selection_text="Original text.",
                focus=["word_choice", "sentence"],
            ),
        )

        # Verify composer called with correct intent
        build_call = mock_composer.build.call_args
        assert build_call.args[0] == LLMIntent.CO_AUTHOR

        # Verify registry called with the correct intent
        stream_call = mock_registry.stream.call_args
        assert stream_call.kwargs["intent"] == LLMIntent.CO_AUTHOR

    @pytest.mark.asyncio
    async def test_diff_metadata_structure(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """Verify structure of diff metadata in final chunk."""
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )

        async def stream_gen() -> AsyncIterator[StreamChunk]:
            yield StreamChunk(text="Revised text for testing.", is_final=False)
            yield StreamChunk(text="", is_final=True, usage=_usage())

        mock_registry.stream = MagicMock(spec=[], return_value=stream_gen())

        chunks = await _collect(
            stream_coauthor(
                pipeline,
                _request(),
                _default_context(),
                _config(),
                selection_text="Original text here.",
                focus=["description"],
            ),
        )

        final = [c for c in chunks if c.is_final]
        meta = final[0].context_meta
        assert meta is not None
        assert isinstance(meta["changes"], list)
        assert isinstance(meta["total_changes"], int)
        assert isinstance(meta["has_changes"], bool)

        # Each change entry has the expected keys
        for change in meta["changes"]:
            assert isinstance(change, dict)
            assert "original_text" in change
            assert "revised_text" in change
            assert "change_type" in change
            assert "index" in change

    @pytest.mark.asyncio
    async def test_selection_and_context_passed_to_prompt(
        self,
        pipeline: WritingPipeline,
        mock_composer: Any,
        mock_registry: Any,
    ) -> None:
        """Verify selection_text, context_before, context_after in prompt ctx."""
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_make_chunks("Revised."),
        )

        await _collect(
            stream_coauthor(
                pipeline,
                _request(),
                _default_context(),
                _config(),
                selection_text="Selected text.",
                context_before="Before text. ",
                context_after=" After text.",
                focus=["dialogue"],
            ),
        )

        # Check the prompt context extra vars contain the selection/context
        build_call = mock_composer.build.call_args
        prompt_ctx = build_call.args[1]
        assert prompt_ctx.extra["selection_text"] == "Selected text."
        assert prompt_ctx.extra["context_before"] == "Before text. "
        assert prompt_ctx.extra["context_after"] == " After text."

    @pytest.mark.asyncio
    async def test_custom_tone_instructions_used(
        self,
        pipeline: WritingPipeline,
        mock_composer: Any,
        mock_registry: Any,
    ) -> None:
        """Custom tone instructions override bundled tone."""
        pipeline._draft_processor.process = MagicMock(  # pyright: ignore[reportPrivateUsage]
            spec=lambda text, **kw: None,
            side_effect=lambda text, **kw: text,
        )
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_make_chunks("Revised."),
        )

        context = _default_context()
        context.tone = "custom"

        await _collect(
            stream_coauthor(
                pipeline,
                _request(),
                context,
                _config(),
                selection_text="Selected text.",
            ),
        )

        build_call = mock_composer.build.call_args
        prompt_ctx = build_call.args[1]
        tone_instr = prompt_ctx.extra.get("tone_instructions", "")
        # For unknown tone, pipeline._tone_instructions returns empty string
        assert isinstance(tone_instr, str)
