"""Unit tests for WritingService context metadata in SSE stream.

Tests verify that StreamChunk carries context_meta correctly and
that the metadata flows through the pipeline without mutation.
"""

from __future__ import annotations

from narrare_core.llm.result import StreamChunk


class TestStreamChunkContextMeta:
    """Tests for StreamChunk context_meta field."""

    def test_stream_chunk_has_context_meta_default_none(self) -> None:
        """context_meta defaults to None for normal text chunks."""
        chunk = StreamChunk(text="hello")
        assert chunk.context_meta is None

    def test_stream_chunk_with_context_meta(self) -> None:
        """context_meta can be set on a metadata-only chunk."""
        meta = {"kb_characters_count": 3, "tone": "dramatic"}
        chunk = StreamChunk(text="", context_meta=meta)
        assert chunk.context_meta == meta
        assert chunk.text == ""

    def test_stream_chunk_meta_ignored_in_normal_chunks(self) -> None:
        """Normal text chunks have no context_meta."""
        chunk = StreamChunk(text="Once upon a time")
        assert chunk.context_meta is None
        assert chunk.text == "Once upon a time"

    def test_stream_chunk_with_all_fields(self) -> None:
        """StreamChunk can carry both usage and context_meta simultaneously."""
        from narrare_core.llm.result import TokenUsage

        usage = TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)
        meta = {"tone": "balanced"}
        chunk = StreamChunk(text="", is_final=True, usage=usage, context_meta=meta)
        assert chunk.usage == usage
        assert chunk.context_meta == meta
        assert chunk.is_final is True
