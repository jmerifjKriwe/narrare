"""Unit tests for InlineSuggestService — mocked dependencies.

Tests verify ghost-text suggestion business logic without touching the
LLM gateway or prompt composer.  All dependencies are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.writing.suggest_service import InlineSuggestService
from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.intents import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_composer() -> MagicMock:
    """Mock PromptComposer."""
    composer = MagicMock(spec=PromptComposer)
    composer.build = AsyncMock(
        return_value=ComposedPrompt(
            system="You are a creative writing assistant.",
            user="Complete this sentence:",
        )
    )
    return composer


@pytest.fixture
def mock_registry() -> MagicMock:
    """Mock ModelRegistry with a streaming method."""

    async def _stream_chunks(**kwargs: object):
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


@pytest.fixture
def suggest_config() -> ResolvedModelConfig:
    """Low-temperature config for inline suggestions."""
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.3,
        max_tokens=60,
    )


@pytest.fixture
def suggest_service(
    mock_composer: MagicMock,
    mock_registry: MagicMock,
    suggest_config: ResolvedModelConfig,
) -> InlineSuggestService:
    """InlineSuggestService with mocked dependencies."""
    return InlineSuggestService(
        registry=mock_registry,
        composer=mock_composer,
        config=suggest_config,
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
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest

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
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest
        from narrare_core.llm.intents import LLMIntent

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
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest

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
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest

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
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="She wondered")

        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            pass

        build_call = mock_composer.build.call_args
        ctx = build_call[0][1]
        assert ctx.extra.get("text_after") == ""

    async def test_suggest_inline_propagates_composer_error(
        self,
        suggest_service: InlineSuggestService,
        mock_composer: MagicMock,
    ) -> None:
        """suggest_inline() propagates errors from prompt composer."""
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest
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
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest

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
        import uuid

        from narrare.writing.schemas import InlineSuggestRequest

        chapter_id = uuid.uuid4()
        user_id = str(uuid.uuid4())
        request = InlineSuggestRequest(text_before="Hello world")

        async for _ in suggest_service.suggest_inline(chapter_id, user_id, request):
            pass

        build_call = mock_composer.build.call_args
        ctx = build_call[0][1]
        assert ctx.language == "en"
