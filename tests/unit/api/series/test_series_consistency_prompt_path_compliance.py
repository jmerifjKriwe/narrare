"""Mode-1 prompt-path compliance test for SeriesConsistencyService (SERIES-004).

Verifies the service routes its system prompt through
``resolve_series_consistency_prompt`` → :func:`compose_invocation` Mode 1
(``LLMIntent.ANALYSE`` + ``context_mode="series_consistency"``) — NOT an
inline f-string, NOT a direct composer call. The governed
``series_consistency`` template IS the system prompt; the Canon entries +
chapter prose flow as user-channel runtime content.

Mirrors ``tests/unit/api/analysis/test_voice_check_prompt_path_compliance.py``
(ADR-046 D.1 precedent) and satisfies the ``analysis/series_consistency: true``
declaration in ``adoption-registry.yaml`` ``prompt_path_compliance``.

Patch note: ``series_consistency_prompt.resolve_series_consistency_prompt``
imports ``compose_invocation`` INSIDE the function (call-time import), so
patching ``narrare_core.ai_invocation.compose_invocation`` intercepts it.

See:
    SERIES-004 — Series Consistency (cross-novel canon check).
    ADR-046 D.1 — prompt-path compliance convention.
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
    CONSTRAINTS.md RULE-02 / RULE-02a / RULE-02b.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from narrare.series.series_consistency_service import SeriesConsistencyService
from narrare_core.agents.series_consistency_types import SeriesConsistencyOutput
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_kb_scope_repo import FakeScopeKBRepo
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

from ._series_consistency_test_helpers import (
    FakeSeriesConsistencyComposer,
    FakeSeriesConsistencyRegistry,
    make_config,
    seed_owned_series_with_canon,
)

_COMPOSED_SYSTEM = "COMPOSED-SERIES-CONSISTENCY-SYSTEM"


class _FakeComposedInvocation:
    """Stand-in for a Mode-1 composed invocation."""

    def __init__(self, system: str = _COMPOSED_SYSTEM, user: str = "") -> None:
        self.composed_prompt = ComposedPrompt(system=system, user=user)


def _make_agent_output() -> SeriesConsistencyOutput:
    return SeriesConsistencyOutput(
        conflicts=[],
        summary="No contradictions between the chapter text and the series Canon.",
    )


def _make_service(
    *,
    series_repo: FakeSeriesRepository,
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
    kb_repo: FakeScopeKBRepo,
    composer: FakeSeriesConsistencyComposer,
) -> SeriesConsistencyService:
    """Build the service with the DEFAULT agent factory (real wiring)."""
    return SeriesConsistencyService(
        series_repo=series_repo,  # type: ignore[arg-type]
        novel_repo=novel_repo,  # type: ignore[arg-type]
        chapter_repo=chapter_repo,  # type: ignore[arg-type]
        kb_repo=kb_repo,  # type: ignore[arg-type]
        registry=FakeSeriesConsistencyRegistry(),  # type: ignore[arg-type]
        config=make_config(),
        composer=composer,  # type: ignore[arg-type]
    )


class TestSeriesConsistencyMode1PromptPath:
    """SeriesConsistencyService resolves its prompt via Mode 1."""

    async def test_compose_invocation_uses_analyse_intent_and_series_mode(self) -> None:
        user_id = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        novel_repo = FakeNovelRepository()
        chapter_repo = FakeChapterRepository()
        kb_repo = FakeScopeKBRepo()
        composer = FakeSeriesConsistencyComposer()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            composer=composer,
        )

        with (
            patch("narrare.series.series_consistency_service.SeriesConsistencyAgent") as MockAgent,
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=_FakeComposedInvocation()),
            ) as mock_compose,
        ):
            MockAgent.return_value.run = AsyncMock(return_value=_make_agent_output())
            await service.check_novel(series_id, novel_id, user_id)

        # Mode 1: exactly one compose_invocation call, no manual injection.
        mock_compose.assert_awaited_once()
        kwargs = mock_compose.call_args.kwargs
        assert kwargs.get("intent") == LLMIntent.ANALYSE
        assert kwargs.get("composer") is composer
        assert kwargs.get("prompt_context") is not None
        assert "manual_injection" not in kwargs
        ctx = kwargs["prompt_context"]
        assert ctx.mode == "series_consistency"
        assert ctx.project_title == "Test Novel"

    async def test_composed_system_prompt_reaches_agent_constructor(self) -> None:
        user_id = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        novel_repo = FakeNovelRepository()
        chapter_repo = FakeChapterRepository()
        kb_repo = FakeScopeKBRepo()
        composer = FakeSeriesConsistencyComposer()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            composer=composer,
        )

        with (
            patch("narrare.series.series_consistency_service.SeriesConsistencyAgent") as MockAgent,
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=_FakeComposedInvocation()),
            ),
        ):
            MockAgent.return_value.run = AsyncMock(return_value=_make_agent_output())
            await service.check_novel(series_id, novel_id, user_id)

        # The governed system prompt is passed as the agent's system prompt —
        # never concatenated into the user-channel run prompt.
        assert MockAgent.call_args.kwargs["system_prompt"] == _COMPOSED_SYSTEM

    async def test_run_prompt_carries_canon_entries_and_chapter_prose(self) -> None:
        user_id = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        novel_repo = FakeNovelRepository()
        chapter_repo = FakeChapterRepository()
        kb_repo = FakeScopeKBRepo()
        composer = FakeSeriesConsistencyComposer()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
            canon_slugs=("character-elara-eye-color",),
            chapter_prose=("Elara's green eyes scanned the horizon.",),
        )
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            composer=composer,
        )

        with (
            patch("narrare.series.series_consistency_service.SeriesConsistencyAgent") as MockAgent,
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=_FakeComposedInvocation()),
            ),
        ):
            mock_run = AsyncMock(return_value=_make_agent_output())
            MockAgent.return_value.run = mock_run
            await service.check_novel(series_id, novel_id, user_id)

        run_prompt = mock_run.call_args.kwargs["prompt"]
        assert "## Series Canon Entries (facts to check against)" in run_prompt
        assert "## Chapter Text (passages to inspect for contradictions)" in run_prompt
        assert "character-elara-eye-color" in run_prompt
        assert "Elara's green eyes scanned the horizon." in run_prompt
        assert _COMPOSED_SYSTEM not in run_prompt

    async def test_no_direct_composer_build_on_happy_path(self) -> None:
        user_id = uuid.uuid4()
        series_repo = FakeSeriesRepository()
        novel_repo = FakeNovelRepository()
        chapter_repo = FakeChapterRepository()
        kb_repo = FakeScopeKBRepo()
        composer = FakeSeriesConsistencyComposer()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )
        service = _make_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            composer=composer,
        )

        with (
            patch("narrare.series.series_consistency_service.SeriesConsistencyAgent") as MockAgent,
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=_FakeComposedInvocation()),
            ),
        ):
            MockAgent.return_value.run = AsyncMock(return_value=_make_agent_output())
            await service.check_novel(series_id, novel_id, user_id)

        # Mode 1 has no direct-build fallback here: a passing composition must
        # never touch composer.build directly.
        assert composer.build_calls == []
