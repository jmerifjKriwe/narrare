"""Unit tests for CoAuthorService.stream_coauthor — context markers.

Tests chapter_content construction with context markers.
All dependencies are mocked (DI pattern, RULE-07).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.writing.coauthor_service import CoAuthorService
from narrare.writing.repository import GenerationRepository
from narrare.writing.schemas_coauthor import CoAuthorFocus, CoAuthorRequest
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.pipeline import WritingPipeline
from tests.unit.api.writing._coauthor_factories import make_static_runtime_factory

if TYPE_CHECKING:
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USAGE = TokenUsage(prompt_tokens=20, completion_tokens=100, total_tokens=120)

CONFIG = ResolvedModelConfig(
    provider_name="test",
    model_id="test-model",
    temperature=0.7,
    max_tokens=4000,
)

_SELECTION = (
    "This is a sufficiently long selection text that demonstrates the "
    "co-author streaming flow. It needs to exceed fifty characters "
    "to satisfy Pydantic's min_length constraint on CoAuthorRequest."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request(**kw: Any) -> CoAuthorRequest:
    """Build a valid CoAuthorRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "selection_text": _SELECTION,
        "focus": [CoAuthorFocus.WORD_CHOICE],
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return CoAuthorRequest(**defaults)


async def _fake_stream(*chunks: StreamChunk) -> Any:
    """Async generator yielding StreamChunks — used as pipeline.generate return."""
    for c in chunks:
        yield c


# ---------------------------------------------------------------------------
# stream_coauthor: context markers
# ---------------------------------------------------------------------------


def _gate_open_repos() -> tuple[AsyncMock, AsyncMock]:
    """S6 gate-open repos (chapter binds to ANY novel, every novel owned)."""
    from tests.factories import make_chapter, make_novel

    chapter_repo = AsyncMock(spec=["get"])
    chapter_repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    novel_repo = AsyncMock(spec=["get_by_id"])
    novel_repo.get_by_id = AsyncMock(return_value=make_novel())
    return chapter_repo, novel_repo


class TestStreamCoauthorContext:
    """Tests for chapter_content construction with context markers."""

    @pytest.mark.asyncio
    async def test_context_markers_included_when_provided(self) -> None:
        """When context_before/context_after provided, content includes markers."""
        request_id = uuid4()
        repo: AsyncMock = AsyncMock(spec=GenerationRepository)
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=request_id)
        repo.get_by_id = AsyncMock(return_value=None)
        repo.update_status = AsyncMock()

        pipeline: MagicMock = MagicMock(spec=WritingPipeline)
        pipeline.generate = MagicMock(
            spec=[],  # type: ignore[method-assign]
            return_value=_fake_stream(
                StreamChunk(text="", is_final=True, usage=USAGE),
            ),
        )

        proc: MagicMock = MagicMock(spec=DraftProcessor)
        proc.process = MagicMock(
            spec=[],  # type: ignore[method-assign]
            side_effect=lambda text, **kw: text,
        )

        cr, nr = _gate_open_repos()
        service = CoAuthorService(
            repo=cast("GenerationRepository", repo),
            runtime_factory=make_static_runtime_factory(cast("WritingPipeline", pipeline), CONFIG),
            draft_processor=cast("DraftProcessor", proc),
            chapter_repo=cast("ChapterRepository", cr),
            novel_repo=cast("NovelRepository", nr),
        )

        req = _request(
            context_before="Before text. ",
            context_after=" After text.",
        )

        async for _ in service.stream_coauthor(uuid4(), uuid4(), str(uuid4()), req):
            pass

        # Verify pipeline was called with content including markers
        generate_call = pipeline.generate.call_args_list[0]
        chapter_content = generate_call.kwargs.get("chapter_content", "")
        assert "Before text. " in chapter_content
        assert "[SELECTION START]" in chapter_content
        assert "[SELECTION END]" in chapter_content
        assert " After text." in chapter_content
        assert _SELECTION in chapter_content

    @pytest.mark.asyncio
    async def test_no_context_markers_when_not_provided(self) -> None:
        """Without context_before/context_after, just selection_text used."""
        request_id = uuid4()
        repo: AsyncMock = AsyncMock(spec=GenerationRepository)
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=request_id)
        repo.get_by_id = AsyncMock(return_value=None)
        repo.update_status = AsyncMock()

        pipeline: MagicMock = MagicMock(spec=WritingPipeline)
        pipeline.generate = MagicMock(
            spec=[],  # type: ignore[method-assign]
            return_value=_fake_stream(
                StreamChunk(text="", is_final=True, usage=USAGE),
            ),
        )

        proc: MagicMock = MagicMock(spec=DraftProcessor)
        proc.process = MagicMock(
            spec=[],  # type: ignore[method-assign]
            side_effect=lambda text, **kw: text,
        )

        cr, nr = _gate_open_repos()
        service = CoAuthorService(
            repo=cast("GenerationRepository", repo),
            runtime_factory=make_static_runtime_factory(cast("WritingPipeline", pipeline), CONFIG),
            draft_processor=cast("DraftProcessor", proc),
            chapter_repo=cast("ChapterRepository", cr),
            novel_repo=cast("NovelRepository", nr),
        )

        req = _request()
        async for _ in service.stream_coauthor(uuid4(), uuid4(), str(uuid4()), req):
            pass

        generate_call = pipeline.generate.call_args_list[0]
        chapter_content = generate_call.kwargs.get("chapter_content", "")
        assert chapter_content == _SELECTION
        assert "[SELECTION START]" not in chapter_content
