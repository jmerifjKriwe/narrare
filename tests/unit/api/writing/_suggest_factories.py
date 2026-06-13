"""Factory functions for InlineSuggestService test mocks.

Shared across ``test_suggest_service.py`` and ``test_suggest_inline.py``
to avoid fixture duplication while keeping each file within RULE-04 limits.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from narrare.chapters.repository import ChapterRepository
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer


def make_mock_composer() -> MagicMock:
    """PromptComposer mock returning a fixed ComposedPrompt."""
    composer = MagicMock(spec=PromptComposer)
    composer.build = AsyncMock(
        return_value=ComposedPrompt(
            system="You are a creative writing assistant.",
            user="Complete this sentence:",
        )
    )
    return composer


def make_mock_registry() -> MagicMock:
    """ModelRegistry mock with a deterministic streaming method."""

    async def _stream_chunks(**kwargs: object) -> object:
        chunks = [
            StreamChunk(text="The old "),
            StreamChunk(text="house "),
            StreamChunk(text="stood at the end of the lane."),
            StreamChunk(text="", is_final=True, usage=TokenUsage(10, 50, 60)),
        ]
        for chunk in chunks:
            yield chunk

    registry = MagicMock(spec=ModelRegistry)
    registry.stream = _stream_chunks
    return registry


def make_suggest_config() -> ResolvedModelConfig:
    """Low-temperature config for inline suggestions."""
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.3,
        max_tokens=60,
    )


def make_mock_chapter_repo() -> MagicMock:
    """ChapterRepository mock returning a simple chapter."""
    chapter = MagicMock(spec=["title", "pov_character_id"])
    chapter.title = "Test Chapter"
    chapter.pov_character_id = None
    repo = MagicMock(spec=ChapterRepository)
    repo.get = AsyncMock(return_value=chapter)
    return repo
