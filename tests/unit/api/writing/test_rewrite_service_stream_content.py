"""Unit tests for RewriteService — chapter_content construction and pipeline kwargs.

Split from test_rewrite_service_stream.py per RULE-04.

Covers:
1. stream_rewrite: chapter_content construction (context markers)
2. stream_rewrite: pipeline kwargs verification (tone, instructions, KB)
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from narrare.writing.rewrite_service import RewriteService
from narrare.writing.schemas_rewrite import RewriteMode, RewriteRequest
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage

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
    "rewrite service streaming flow. It needs to exceed fifty characters "
    "to satisfy Pydantic's min_length constraint on RewriteRequest."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request(**kw: Any) -> RewriteRequest:
    """Create a RewriteRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "selection_text": _SELECTION,
        "mode": RewriteMode.TONE,
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return RewriteRequest(**defaults)


async def _fake_stream(*texts: str) -> Any:
    """Async generator yielding StreamChunks — used as pipeline.generate return."""
    for t in texts:
        yield StreamChunk(text=t)
    yield StreamChunk(text="", is_final=True, usage=USAGE)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_pipeline() -> MagicMock:
    """Pipeline mock — MagicMock so generate() returns async generator directly."""
    pipeline = MagicMock(spec=["generate"])
    pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Default."))
    return pipeline


@pytest.fixture()
def mock_draft_processor() -> MagicMock:
    proc = MagicMock(spec=["process"])
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return proc


@pytest.fixture()
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_active_for_chapter = AsyncMock(return_value=None)
    repo.create_if_no_active = AsyncMock(return_value=uuid.uuid4())
    repo.update_status = AsyncMock()
    return repo


@pytest.fixture()
def service(
    mock_repo: AsyncMock,
    mock_pipeline: MagicMock,
    mock_draft_processor: MagicMock,
) -> RewriteService:
    """RewriteService with mocked dependencies (no tone/relationship services)."""
    from tests.factories import make_chapter, make_novel

    # S6 gate-open repos (chapter binds to ANY novel, every novel owned):
    # these tests exercise streaming behavior, not ownership — the access
    # matrix lives in test_generation_access_matrix.py.
    chapter_repo = AsyncMock(spec=["get"])
    chapter_repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    novel_repo = AsyncMock(spec=["get_by_id"])
    novel_repo.get_by_id = AsyncMock(return_value=make_novel())
    return RewriteService(
        repo=mock_repo,
        pipeline=mock_pipeline,
        draft_processor=mock_draft_processor,
        config=CONFIG,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )


# ---------------------------------------------------------------------------
# stream_rewrite: chapter_content construction
# ---------------------------------------------------------------------------


class TestChapterContentConstruction:
    async def test_context_after_without_context_before(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """context_after triggers markers even without context_before (211->213 branch)."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(context_before=None, context_after="After text only.")
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        cc = mock_pipeline.generate.call_args.kwargs.get("chapter_content", "")
        # context_before is None → only [SELECTION START] + text + [SELECTION END] + after
        assert "[SELECTION START]" in cc
        assert "[SELECTION END]" in cc
        assert "After text only." in cc
        # Should NOT include an empty line for context_before
        assert cc.count("\n") >= 2

    async def test_plain_selection_text_when_no_context(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """Without context_before/context_after, chapter_content is just selection_text."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(context_before=None, context_after=None)
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        cc = mock_pipeline.generate.call_args.kwargs.get("chapter_content", "")
        assert cc == req.selection_text
        assert "[SELECTION START]" not in cc

    async def test_context_before_included(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """context_before appears above the selection marker."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(context_before="Earlier in the chapter...")
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        cc = mock_pipeline.generate.call_args.kwargs.get("chapter_content", "")
        assert "Earlier in the chapter..." in cc
        assert "[SELECTION START]" in cc
        assert "[SELECTION END]" in cc
        assert req.selection_text in cc

    async def test_context_before_and_after_included(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """Both context_before and context_after appear with markers."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(
            context_before="Before text. ",
            context_after="After text.",
        )
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        cc = mock_pipeline.generate.call_args.kwargs.get("chapter_content", "")
        assert "Before text." in cc
        assert "[SELECTION START]" in cc
        assert req.selection_text in cc
        assert "[SELECTION END]" in cc
        assert "After text." in cc


# ---------------------------------------------------------------------------
# stream_rewrite: pipeline kwargs verification
# ---------------------------------------------------------------------------


class TestPipelineKwargs:
    async def test_rewrite_mode_passed_to_pipeline(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """The rewrite mode value is passed as rewrite_mode kwarg."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(mode=RewriteMode.STYLE)
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        kw = mock_pipeline.generate.call_args.kwargs
        assert kw.get("rewrite_mode") == "style"

    async def test_custom_instructions_passed(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """Custom instructions from request are forwarded."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(custom_instructions="Make it more poetic")
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        kw = mock_pipeline.generate.call_args.kwargs
        assert kw.get("custom_instructions") == "Make it more poetic"

    async def test_rewrite_count_passed(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """Number of alternatives (count) forwarded to pipeline."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(count=3)
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        kw = mock_pipeline.generate.call_args.kwargs
        assert kw.get("rewrite_count") == 3

    async def test_selection_text_passed(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """selection_text forwarded as pipeline kwarg."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request()
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        kw = mock_pipeline.generate.call_args.kwargs
        assert kw.get("selection_text") == req.selection_text

    async def test_context_before_defaults_to_empty_string(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """context_before defaults to '' when not provided."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(context_before=None)
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        kw = mock_pipeline.generate.call_args.kwargs
        assert kw.get("context_before") == ""

    async def test_context_after_defaults_to_empty_string(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """context_after defaults to '' when not provided."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(context_after=None)
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        kw = mock_pipeline.generate.call_args.kwargs
        assert kw.get("context_after") == ""

    async def test_kb_relationships_passed(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """KB relationships text is forwarded (FIND-009 path).

        With relationship_repo=None, fetch_formatted_relationships returns
        empty RenderedKBContext, so kb_relationships should be an empty string.
        """
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        async for _ in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        kw = mock_pipeline.generate.call_args.kwargs
        # relationship_repo is None in test fixture → empty string
        assert kw.get("kb_relationships") == ""

    async def test_custom_tone_instructions_none_for_bundled_tone(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """Bundled tone 'balanced' produces None custom_tone_instructions."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(tone="balanced")
        async for _ in service.stream_rewrite(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        kw = mock_pipeline.generate.call_args.kwargs
        assert kw.get("custom_tone_instructions") is None
