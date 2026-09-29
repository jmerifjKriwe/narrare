"""Unit tests for ChapterSummaryService — mocked dependencies.

Tests verify service business logic without touching the database,
LLM gateway, or prompt composer. All dependencies are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.usage import UsageLimits

from narrare.writing.summary_service import ChapterSummaryService
from narrare_core.llm import ResolvedModelConfig
from narrare_core.prompts.composer import ComposedPrompt
from narrare_core.shared.errors import NotFoundError, WritingError

TEST_USER_ID = "00000000-0000-0000-0000-0000000000aa"  # novel owner in these tests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> ResolvedModelConfig:
    """Create a default ResolvedModelConfig for tests."""
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.3,
        max_tokens=1000,
    )


def _make_composer() -> AsyncMock:
    """Create a mock PromptComposer that returns a ComposedPrompt."""
    composer = AsyncMock()
    composer.build = AsyncMock(
        return_value=ComposedPrompt(
            system="You are a summarizer.",
            user="Summarize this content.",
        )
    )
    return composer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_registry() -> AsyncMock:
    """Mock ModelRegistry with the prepare() assembly point (Task 6c)."""
    from pydantic_ai.models import Model

    from narrare_core.llm._prepared_call import PreparedModelCall

    registry = AsyncMock()
    model_mock = MagicMock(spec=Model)
    registry.get_model = AsyncMock(return_value=model_mock)
    registry.prepare = AsyncMock(
        return_value=PreparedModelCall(
            model=model_mock,
            model_settings={"max_tokens": 1000},
            usage_limits=None,
        )
    )
    return registry


@pytest.fixture
def mock_chapter_repo() -> AsyncMock:
    """Mock ChapterRepository."""
    repo = AsyncMock()
    repo.get = AsyncMock(return_value=None)
    repo.update_summary = AsyncMock()
    return repo


@pytest.fixture
def mock_novel_repo() -> AsyncMock:
    """Mock NovelRepository — every novel belongs to TEST_USER_ID (gate passes)."""
    from tests.factories import make_novel

    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=make_novel())
    return repo


@pytest.fixture
def config() -> ResolvedModelConfig:
    return _make_config()


@pytest.fixture
def mock_composer() -> AsyncMock:
    return _make_composer()


@pytest.fixture
def service(
    mock_registry: AsyncMock,
    config: ResolvedModelConfig,
    mock_chapter_repo: AsyncMock,
    mock_novel_repo: AsyncMock,
    mock_composer: AsyncMock,
) -> ChapterSummaryService:
    from tests.unit.api.writing._writing_factories import make_static_summary_runtime_factory

    return ChapterSummaryService(
        registry=mock_registry,
        # ADR-086 L38: the service composes its runtime at first use; the
        # fake chain pins a fixed runtime (render- and outcome-inert —
        # same config/credentials the eager factory passed).
        runtime_factory=make_static_summary_runtime_factory(config),
        chapter_repo=mock_chapter_repo,
        novel_repo=mock_novel_repo,
        composer=mock_composer,
    )


# ---------------------------------------------------------------------------
# Test ChapterSummaryService.summarize
# ---------------------------------------------------------------------------


class TestSummarize:
    """Tests for ChapterSummaryService.summarize()."""

    async def test_summarize_with_valid_chapter_returns_summary(
        self,
        service: ChapterSummaryService,
        mock_chapter_repo: AsyncMock,
        mock_composer: AsyncMock,
    ) -> None:
        """Happy path: valid chapter content produces a summary."""
        from narrare_core.agents.summary_types import SummaryOutput
        from tests.factories import make_chapter

        chapter = make_chapter(content="Once upon a time in a faraway land...", title="Chapter 1")
        mock_chapter_repo.get = AsyncMock(return_value=chapter)

        # Patch ChapterSummaryAgent to return controlled output
        mock_agent = AsyncMock()
        mock_output = MagicMock(spec=SummaryOutput)
        mock_output.summary = "A hero begins their journey."
        mock_output.word_count = 5
        mock_output.key_points = ["Hero introduction"]
        mock_agent.run = AsyncMock(return_value=mock_output)

        with patch(
            "narrare.writing._summary_invocation.ChapterSummaryAgent",
            return_value=mock_agent,
        ):
            result = await service.summarize(
                chapter_id=chapter.id,
                max_sentences=3,
                language="en",
                user_id=TEST_USER_ID,
            )

        assert result.summary == "A hero begins their journey."
        assert result.word_count == 5
        assert result.key_points == ["Hero introduction"]
        mock_chapter_repo.update_summary.assert_awaited_once_with(
            chapter, "A hero begins their journey."
        )
        # Verify composer was called
        mock_composer.build.assert_awaited_once()

    async def test_summarize_with_empty_content_returns_empty(
        self,
        service: ChapterSummaryService,
        mock_chapter_repo: AsyncMock,
    ) -> None:
        """Edge case: chapter with no content returns an empty result."""
        from tests.factories import make_chapter

        chapter = make_chapter(content="", title="Empty Chapter")
        mock_chapter_repo.get = AsyncMock(return_value=chapter)

        result = await service.summarize(chapter_id=chapter.id, user_id=TEST_USER_ID)

        assert result.summary == ""
        assert result.word_count == 0
        assert result.key_points == []
        mock_chapter_repo.update_summary.assert_not_called()

    async def test_summarize_with_nonexistent_chapter_raises_not_found(
        self,
        service: ChapterSummaryService,
        mock_chapter_repo: AsyncMock,
    ) -> None:
        """Error: requesting a non-existent chapter raises NotFoundError."""
        mock_chapter_repo.get = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError, match="Chapter"):
            await service.summarize(
                chapter_id="00000000-0000-0000-0000-000000000001",  # type: ignore[arg-type]
                user_id=TEST_USER_ID,
            )

    async def test_summarize_when_llm_fails_raises_writing_error(
        self,
        service: ChapterSummaryService,
        mock_chapter_repo: AsyncMock,
    ) -> None:
        """Error: LLM failure is wrapped in WritingError."""
        from tests.factories import make_chapter

        chapter = make_chapter(content="Some content here...", title="Test")
        mock_chapter_repo.get = AsyncMock(return_value=chapter)

        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(
            side_effect=ValueError("LLM service unavailable"),
        )

        with (
            patch(
                "narrare.writing._summary_invocation.ChapterSummaryAgent",
                return_value=mock_agent,
            ),
            pytest.raises(WritingError, match="Chapter summarization failed"),
        ):
            await service.summarize(chapter_id=chapter.id, user_id=TEST_USER_ID)

        mock_chapter_repo.update_summary.assert_not_called()

    async def test_summarize_when_agent_raises_not_found_re_raises(
        self,
        service: ChapterSummaryService,
        mock_chapter_repo: AsyncMock,
    ) -> None:
        """NotFoundError from agent is re-raised (line 152)."""
        from narrare_core.shared.errors import NotFoundError
        from tests.factories import make_chapter

        chapter = make_chapter(content="Some content here...", title="Test")
        mock_chapter_repo.get = AsyncMock(return_value=chapter)

        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(
            side_effect=NotFoundError("Chapter", identifier=str(chapter.id)),
        )

        with (
            patch(
                "narrare.writing._summary_invocation.ChapterSummaryAgent",
                return_value=mock_agent,
            ),
            pytest.raises(NotFoundError, match="Chapter"),
        ):
            await service.summarize(chapter_id=chapter.id, user_id=TEST_USER_ID)

    async def test_summarize_uses_composer_for_prompt(
        self,
        service: ChapterSummaryService,
        mock_chapter_repo: AsyncMock,
        mock_registry: AsyncMock,
        mock_composer: AsyncMock,
    ) -> None:
        """Verify that the service uses PromptComposer to build prompts."""
        from narrare_core.agents.summary_types import SummaryOutput
        from narrare_core.llm import LLMIntent
        from tests.factories import make_chapter

        chapter = make_chapter(content="Test content for chapter.", title="Test")
        mock_chapter_repo.get = AsyncMock(return_value=chapter)

        mock_agent = AsyncMock()
        mock_output = MagicMock(spec=SummaryOutput)
        mock_output.summary = "A test summary."
        mock_output.word_count = 3
        mock_output.key_points = []
        mock_agent.run = AsyncMock(return_value=mock_output)

        with patch(
            "narrare.writing._summary_invocation.ChapterSummaryAgent",
            return_value=mock_agent,
        ):
            await service.summarize(
                chapter_id=chapter.id,
                max_sentences=5,
                language="de",
                user_id=TEST_USER_ID,
            )

        # Verify the composer was called with the correct intent
        mock_composer.build.assert_awaited_once()
        call_args = mock_composer.build.call_args
        assert call_args[0][0] == LLMIntent.SUMMARIZE

        # Verify the registry resolved via the prepare() assembly point
        # with the SUMMARIZE intent (Task 6c wiring). The config triple now
        # arrives through the frozen first-use runtime (ADR-086 L38).
        runtime = await service.ensure_resolved()
        mock_registry.prepare.assert_awaited_once_with(
            runtime.config,
            intent=LLMIntent.SUMMARIZE,
            # Task 3: the ADR-045 run-limit resolver applies the config's
            # output cap (max_tokens=1000) at the agent boundary.
            usage_limits=UsageLimits(output_tokens_limit=1000),
            api_key=None,
            base_url=None,
        )

        # Verify the agent was called with the composed user prompt
        mock_agent.run.assert_awaited_once()
        agent_await_args = mock_agent.run.await_args
        assert agent_await_args is not None
        assert agent_await_args.kwargs["deps"].language == "de"
        assert agent_await_args.kwargs["deps"].max_sentences == 5
        assert agent_await_args.kwargs["deps"].chapter_title == "Test"
