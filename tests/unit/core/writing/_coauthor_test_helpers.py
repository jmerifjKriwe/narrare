"""Shared helper functions for co-author pipeline tests.

These are imported by both ``conftest.py`` (for fixtures) and individual
test files.  The module is prefixed with ``_`` to exclude it from test
collection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__: list[str] = [
    "_collect",
    "_config",
    "_default_context",
    "_make_chunks",
    "_request",
    "_usage",
]
from uuid import uuid4

from narrare_core.llm.intents import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.writing import GenerationMode
from narrare_core.writing.models import GenerationRequest, WritingContext

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=2000,
        streams=True,
    )


def _usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)


def _request(
    mode: GenerationMode = GenerationMode.CO_AUTHOR,
) -> GenerationRequest:
    return GenerationRequest(
        chapter_id=uuid4(),
        project_id=uuid4(),
        user_id=uuid4(),
        mode=mode,
        writing_language="en",
    )


def _default_context() -> WritingContext:
    return WritingContext(
        chapter_content="Original text.",
        project_title="Test Novel",
        genre="fantasy",
        language="en",
        tone="balanced",
        character_voice_profiles="",
        user_preferences="",
        avoidance_patterns="",
    )


async def _collect(iterator: AsyncIterator[StreamChunk]) -> list[StreamChunk]:
    chunks: list[StreamChunk] = []
    async for chunk in iterator:
        chunks.append(chunk)
    return chunks


def _make_chunks(*texts: str) -> AsyncIterator[StreamChunk]:
    """Create an async iterator of text chunks with a final chunk."""

    async def gen() -> AsyncIterator[StreamChunk]:
        for text in texts[:-1]:
            yield StreamChunk(text=text)
        yield StreamChunk(text=texts[-1], is_final=True, usage=_usage())

    return gen()
