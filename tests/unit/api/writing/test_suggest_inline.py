"""Unit tests for InlineSuggestService.suggest_inline — streaming behaviour.

Split from ``test_suggest_service.py`` to comply with RULE-04 file-size limits.
All dependencies are mocked via factory functions in ``_suggest_factories.py``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.writing.schemas import InlineSuggestRequest
from narrare.writing.suggest_service import InlineSuggestService
from tests.unit.api.writing._suggest_factories import (
    make_mock_chapter_repo,
    make_mock_composer,
    make_mock_registry,
    make_suggest_resolved,
)

if TYPE_CHECKING:
    from narrare._app.dependencies_services import StaticModelResolution

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_composer() -> MagicMock:
    return make_mock_composer()


@pytest.fixture
def mock_registry() -> MagicMock:
    return make_mock_registry()


@pytest.fixture
def suggest_resolution() -> StaticModelResolution:
    """Fixed resolution wrapping the low-temperature suggest config."""
    from narrare._app.dependencies_services import StaticModelResolution

    return StaticModelResolution(make_suggest_resolved())


@pytest.fixture
def mock_chapter_repo() -> MagicMock:
    return make_mock_chapter_repo()


@pytest.fixture
def suggest_service(
    mock_composer: MagicMock,
    mock_registry: MagicMock,
    mock_chapter_repo: MagicMock,
    suggest_resolution: StaticModelResolution,
) -> InlineSuggestService:
    """InlineSuggestService with mocked dependencies."""
    from tests.unit.api.writing._suggest_factories import make_mock_novel_repo

    return InlineSuggestService(
        registry=mock_registry,
        composer=mock_composer,
        model_resolution=suggest_resolution,
        chapter_repo=mock_chapter_repo,
        novel_repo=make_mock_novel_repo(),
    )


# ---------------------------------------------------------------------------
# suggest_inline
# ---------------------------------------------------------------------------


class TestSuggestInline:
    """Tests for the ghost-text inline suggestion endpoint."""

    async def test_suggest_inline_returns_streamed_chunks(
        self,
        suggest_service: InlineSuggestService,
    ) -> None:
        """suggest_inline() yields StreamChunks from the model registry."""

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="The old house")

        results: list[str] = []
        async for chunk in suggest_service.suggest_inline(chapter_id, user_id, request):
            results.append(chunk.text)
            if chunk.is_final:
                assert chunk.usage is not None

        assert len(results) == 4
        assert results[0] == "The old "
        assert results[1] == "house "
        assert results[-1] == ""  # final empty chunk

    async def test_suggest_inline_uses_prompt_composer(
        self,
        suggest_service: InlineSuggestService,
        mock_composer: MagicMock,
    ) -> None:
        """suggest_inline() calls prompt composer with SUGGEST intent."""
        from narrare_core.llm import LLMIntent

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="Once upon a time")

        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            pass

        mock_composer.build.assert_called_once()
        call_args = mock_composer.build.call_args
        assert call_args[0][0] == LLMIntent.SUGGEST

    async def test_suggest_inline_uses_model_registry_stream(
        self,
        suggest_service: InlineSuggestService,
        mock_registry: MagicMock,
    ) -> None:
        """suggest_inline() streams via ModelRegistry.stream()."""

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="The sun was setting")

        # Verify stream was invoked by consuming all chunks
        chunks_consumed = 0
        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            chunks_consumed += 1

        assert chunks_consumed > 0

    async def test_suggest_inline_with_text_after(
        self,
        suggest_service: InlineSuggestService,
        mock_composer: MagicMock,
    ) -> None:
        """suggest_inline() includes text_after in prompt context."""

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(
            text_before="He walked into the ",
            text_after=" and sat down.",
        )

        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            pass

        # Verify text_after was passed via context extra
        build_call = mock_composer.build.call_args
        ctx = build_call[0][1]
        assert ctx.extra.get("text_after") == " and sat down."

    async def test_suggest_inline_empty_text_after_defaults_to_empty(
        self,
        suggest_service: InlineSuggestService,
        mock_composer: MagicMock,
    ) -> None:
        """suggest_inline() defaults text_after to '' when not provided."""

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="She wondered")

        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            pass

        build_call = mock_composer.build.call_args
        ctx = build_call[0][1]
        assert ctx.extra.get("text_after") == ""

    async def test_suggest_inline_supplies_text_before_via_extra_not_author_instructions(
        self,
        suggest_service: InlineSuggestService,
        mock_composer: MagicMock,
    ) -> None:
        """R2-B' un-mapping pin: text_before reaches the SYSTEM channel via
        extra (XML-wrapped by the governed template) and must NOT be set as
        author_instructions — the composer's L170 fallback would otherwise
        duplicate the raw manuscript text into the user channel."""
        sentinel = "The lighthouse blinked twice."

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before=sentinel)

        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            pass

        build_call = mock_composer.build.call_args
        ctx = build_call[0][1]
        assert ctx.extra.get("text_before") == sentinel
        assert ctx.author_instructions == ""

    async def test_suggest_inline_supplies_empty_kb_characters(
        self,
        suggest_service: InlineSuggestService,
        mock_composer: MagicMock,
    ) -> None:
        """R2-B' lean ruling: no KB assembly on the <500 ms path —
        kb_characters is supplied empty so the route renders the Characters
        section empty instead of raising PromptVariableError."""
        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="Morning fog gathered.")

        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            pass

        build_call = mock_composer.build.call_args
        ctx = build_call[0][1]
        assert ctx.extra.get("kb_characters") == ""

    async def test_suggest_inline_propagates_composer_error(
        self,
        suggest_service: InlineSuggestService,
        mock_composer: MagicMock,
    ) -> None:
        """suggest_inline() propagates errors from prompt composer."""
        from narrare_core.shared.errors import PromptNotFoundError

        mock_composer.build = AsyncMock(
            side_effect=PromptNotFoundError("writing", "en", "inline_suggest")
        )

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="Hello")

        with pytest.raises(PromptNotFoundError):
            async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
                pass  # pragma: no cover

    async def test_suggest_inline_passes_language_to_prompt_context(
        self,
        suggest_service: InlineSuggestService,
        mock_composer: MagicMock,
    ) -> None:
        """suggest_inline() uses the language from the request, not a hardcoded value."""

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="Der alte Mann", language="de")

        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            pass

        build_call = mock_composer.build.call_args
        ctx = build_call[0][1]
        assert ctx.language == "de"

    async def test_suggest_inline_defaults_language_to_en(
        self,
        suggest_service: InlineSuggestService,
        mock_composer: MagicMock,
    ) -> None:
        """suggest_inline() defaults to 'en' when language is not explicitly set."""

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="Hello world")

        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            pass

        build_call = mock_composer.build.call_args
        ctx = build_call[0][1]
        assert ctx.language == "en"

    async def test_suggest_inline_chapter_none_raises_not_found(
        self,
        suggest_service: InlineSuggestService,
        mock_chapter_repo: MagicMock,
    ) -> None:
        """Unknown chapter → NotFoundError from the S6 ownership gate.

        Pre-S6 this streamed gracefully with an empty chapter context —
        exactly the existence-oracle the IDOR remediation removes; the
        access matrix (``test_generation_access_matrix.py``) pins the
        foreign ≡ unknown shape.
        """
        from narrare_core.shared.errors import NotFoundError

        mock_chapter_repo.get = AsyncMock(return_value=None)

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="Hello world")

        with pytest.raises(NotFoundError, match="Chapter"):
            async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
                pass

        mock_chapter_repo.get.assert_called_with(chapter_id)

    async def test_suggest_inline_with_pov_in_context(
        self,
        suggest_service: InlineSuggestService,
        mock_chapter_repo: MagicMock,
        mock_composer: MagicMock,
    ) -> None:
        """build_chapter_context includes POV when set."""

        chapter = MagicMock(spec=["title", "pov_character_id", "novel_id"])
        chapter.title = "Test Chapter"
        chapter.pov_character_id = "pov-123"
        chapter.novel_id = uuid.uuid4()
        mock_chapter_repo.get = AsyncMock(return_value=chapter)

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="Hello world")

        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            pass

        # POV should be in the extra context
        build_call = mock_composer.build.call_args
        ctx = build_call[0][1]
        assert "pov-123" in str(ctx.extra) or "pov-123" in str(ctx.extra.get("chapter_context", ""))
