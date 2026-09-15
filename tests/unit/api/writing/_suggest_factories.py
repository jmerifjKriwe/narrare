"""Factory functions for InlineSuggestService test mocks.

Shared across ``test_suggest_service.py`` and ``test_suggest_inline.py``
to avoid fixture duplication while keeping each file within RULE-04 limits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from narrare.chapters.repository import ChapterRepository
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer

if TYPE_CHECKING:
    from narrare.novels.repository import NovelRepository
    from narrare.writing.suggest_service import InlineSuggestService


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


def make_suggest_resolved() -> ResolvedModel:
    """Fixed model triple wrapping :func:`make_suggest_config`.

    Post-ADR-086 the service takes a ``ModelResolution`` instead of a
    bare config; tests feed it via ``StaticModelResolution``.
    """
    return ResolvedModel(
        config=make_suggest_config(),
        api_key=None,
        base_url=None,
        source="unit-test",
    )


def make_mock_chapter_repo() -> MagicMock:
    """ChapterRepository mock returning a simple chapter."""
    chapter = MagicMock(spec=["title", "pov_character_id", "novel_id"])
    chapter.title = "Test Chapter"
    chapter.pov_character_id = None
    chapter.novel_id = uuid4()
    repo = MagicMock(spec=ChapterRepository)
    repo.get = AsyncMock(return_value=chapter)
    return repo


def make_mock_novel_repo() -> MagicMock:
    """NovelRepository mock — every novel belongs to the caller (S6 gate open)."""
    from narrare.novels.repository import NovelRepository
    from tests.factories import make_novel

    repo = MagicMock(spec=NovelRepository)
    repo.get_by_id = AsyncMock(return_value=make_novel())
    return repo


def make_matrix_suggest_service(
    *,
    registry_guarded: bool,
    chapter_repo: ChapterRepository,
    novel_repo: NovelRepository,
    config: ResolvedModelConfig,
) -> InlineSuggestService:
    """Build the access-matrix InlineSuggestService over its fakes.

    Extracted from ``test_generation_access_matrix.py`` per RULE-04 (the
    ADR-086 L32 extend branch pushed the matrix file over its 400-line
    limit); behavior is unchanged — only the location moved.

    ``registry_guarded=True`` (the matrix's ``working_llm=False``) arms a
    guard that fails the test the moment ``registry.stream`` (the real
    LLM boundary) is reached.
    """
    from narrare._app.dependencies_services import StaticModelResolution
    from narrare.writing.suggest_service import InlineSuggestService

    registry = make_mock_registry()
    if registry_guarded:

        def _must_not_stream(**kwargs: object) -> Any:
            raise AssertionError("registry invoked — LLM call despite the gate")

        registry.stream = _must_not_stream
    return InlineSuggestService(
        registry=registry,
        composer=make_mock_composer(),
        model_resolution=StaticModelResolution(ResolvedModel(config=config)),
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )
