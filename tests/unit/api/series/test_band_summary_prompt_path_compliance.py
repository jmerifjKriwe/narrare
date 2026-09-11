"""Mode-1 prompt-path compliance test for BandSummaryService (SERIES-002).

Verifies the service routes its system prompt through
:func:`compose_invocation` Mode 1 (``LLMIntent.SUMMARIZE`` +
``context_mode="band_summary"``) — NOT an inline f-string, NOT a direct
composer call (the direct ``composer.build`` fallback must stay untaken on the
happy path). The governed ``band_summary`` template IS the system prompt; the
numbered chapter summaries flow as user-channel runtime content.

Mirrors ``tests/unit/api/analysis/test_voice_check_prompt_path_compliance.py``
(ADR-046 D.1 precedent) and satisfies the ``analysis/band_summary: true``
declaration in ``adoption-registry.yaml`` ``prompt_path_compliance``.

See:
    SERIES-002 — Series Band Summary.
    ADR-046 D.1 — prompt-path compliance convention.
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-02 / RULE-02a / RULE-02b.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from narrare.series.band_summary_service import BandSummaryService
from narrare_core.agents.band_summary_types import BandSummaryOutput
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt
from tests.factories import make_chapter, make_novel
from tests.fakes.fake_band_summary_repo import FakeBandSummaryRepository
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository

from ._band_summary_test_helpers import (
    FakeBandSummaryComposer,
    FakeBandSummaryRegistry,
    make_band_summary_config,
)

_COMPOSED_SYSTEM = "COMPOSED-BAND-SUMMARY-SYSTEM"


class _FakeComposedInvocation:
    """Stand-in for a Mode-1 composed invocation."""

    def __init__(self, system: str = _COMPOSED_SYSTEM, user: str = "") -> None:
        self.composed_prompt = ComposedPrompt(system=system, user=user)


def _make_agent_output() -> BandSummaryOutput:
    return BandSummaryOutput(
        full_summary="The hero prevails and the realm is restored.",
        short_summary="A hero restores a fractured realm.",
    )


def _make_service(
    *,
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
    composer: FakeBandSummaryComposer,
) -> BandSummaryService:
    """Build the service with the DEFAULT agent factory (real wiring)."""
    return BandSummaryService(
        repo=FakeBandSummaryRepository(),
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        registry=FakeBandSummaryRegistry(),  # type: ignore[arg-type]
        config=make_band_summary_config(),
        composer=composer,  # type: ignore[arg-type]
    )


def _seed_novel_with_summaries(
    novel_repo: FakeNovelRepository, chapter_repo: FakeChapterRepository
) -> uuid.UUID:
    novel_id = uuid.uuid4()
    novel_repo.seed(make_novel(id=novel_id, title="The Forbidden Vale", genre="Fantasy"))
    chapter_repo.seed(
        make_chapter(novel_id=novel_id, position=1, summary="Hero arrives."),
        make_chapter(novel_id=novel_id, position=2, summary="Secret revealed."),
    )
    return novel_id


class TestBandSummaryMode1PromptPath:
    """BandSummaryService resolves its prompt via compose_invocation Mode 1."""

    async def test_compose_invocation_uses_summarize_intent_and_band_summary_mode(
        self,
    ) -> None:
        novel_repo = FakeNovelRepository()
        chapter_repo = FakeChapterRepository()
        composer = FakeBandSummaryComposer()
        novel_id = _seed_novel_with_summaries(novel_repo, chapter_repo)
        service = _make_service(novel_repo=novel_repo, chapter_repo=chapter_repo, composer=composer)

        with (
            patch("narrare.series.band_summary_service.BandSummaryAgent") as MockAgent,
            patch(
                "narrare.series.band_summary_prompt.compose_invocation",
                new=AsyncMock(return_value=_FakeComposedInvocation()),
            ) as mock_compose,
        ):
            MockAgent.return_value.run = AsyncMock(return_value=_make_agent_output())
            await service.generate(novel_id)

        # Mode 1: exactly one compose_invocation call, no manual injection.
        mock_compose.assert_awaited_once()
        kwargs = mock_compose.call_args.kwargs
        assert kwargs.get("intent") == LLMIntent.SUMMARIZE
        assert kwargs.get("composer") is composer
        assert kwargs.get("prompt_context") is not None
        assert "manual_injection" not in kwargs
        ctx = kwargs["prompt_context"]
        assert ctx.mode == "band_summary"
        assert ctx.project_title == "The Forbidden Vale"
        assert ctx.genre == "Fantasy"

    async def test_composed_system_prompt_reaches_agent_constructor(self) -> None:
        novel_repo = FakeNovelRepository()
        chapter_repo = FakeChapterRepository()
        composer = FakeBandSummaryComposer()
        novel_id = _seed_novel_with_summaries(novel_repo, chapter_repo)
        service = _make_service(novel_repo=novel_repo, chapter_repo=chapter_repo, composer=composer)

        with (
            patch("narrare.series.band_summary_service.BandSummaryAgent") as MockAgent,
            patch(
                "narrare.series.band_summary_prompt.compose_invocation",
                new=AsyncMock(return_value=_FakeComposedInvocation()),
            ),
        ):
            MockAgent.return_value.run = AsyncMock(return_value=_make_agent_output())
            await service.generate(novel_id)

        # The governed system prompt is passed as the agent's system prompt —
        # never concatenated into the user-channel run prompt.
        assert MockAgent.call_args.kwargs["system_prompt"] == _COMPOSED_SYSTEM

    async def test_run_prompt_carries_numbered_chapter_summaries(self) -> None:
        novel_repo = FakeNovelRepository()
        chapter_repo = FakeChapterRepository()
        composer = FakeBandSummaryComposer()
        novel_id = _seed_novel_with_summaries(novel_repo, chapter_repo)
        service = _make_service(novel_repo=novel_repo, chapter_repo=chapter_repo, composer=composer)

        with (
            patch("narrare.series.band_summary_service.BandSummaryAgent") as MockAgent,
            patch(
                "narrare.series.band_summary_prompt.compose_invocation",
                new=AsyncMock(return_value=_FakeComposedInvocation()),
            ),
        ):
            mock_run = AsyncMock(return_value=_make_agent_output())
            MockAgent.return_value.run = mock_run
            await service.generate(novel_id)

        run_prompt = mock_run.call_args.kwargs["prompt"]
        assert "1. Hero arrives." in run_prompt
        assert "2. Secret revealed." in run_prompt
        assert _COMPOSED_SYSTEM not in run_prompt

    async def test_no_direct_composer_build_fallback_on_happy_path(self) -> None:
        novel_repo = FakeNovelRepository()
        chapter_repo = FakeChapterRepository()
        composer = FakeBandSummaryComposer()
        novel_id = _seed_novel_with_summaries(novel_repo, chapter_repo)
        service = _make_service(novel_repo=novel_repo, chapter_repo=chapter_repo, composer=composer)

        with (
            patch("narrare.series.band_summary_service.BandSummaryAgent") as MockAgent,
            patch(
                "narrare.series.band_summary_prompt.compose_invocation",
                new=AsyncMock(return_value=_FakeComposedInvocation()),
            ),
        ):
            MockAgent.return_value.run = AsyncMock(return_value=_make_agent_output())
            await service.generate(novel_id)

        # The direct composer.build fallback exists for pipeline hiccups only;
        # a passing Mode-1 path must leave it untaken.
        assert composer.build_calls == []
