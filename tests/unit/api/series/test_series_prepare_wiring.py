"""Task 6d-2 wiring tests — series domain resolves via ModelRegistry.prepare().

Pins the Task-6a/6b/6c structural contract for the two bare ``get_model`` +
``agent.run()`` series call sites — each resolves the model via the SINGLE
assembly point (``ModelRegistry.prepare``, Task 4) and forwards the coherent
``(model, model_settings, usage_limits)`` triple to ``agent.run``:

- ``SeriesConsistencyService.check_novel`` (ANALYSE)
- ``BandSummaryService.generate`` (SUMMARIZE)

Root cause pinned here (structural audit, "Pipeline 3 — nothing at
all"): the sites resolved the model via bare ``get_model`` and called
``agent.run()`` with NO model_settings and NO usage_limits, so the
intent-aware thinking policy and the ADR-045 output cap never applied
to these series paths. The capability intent is a static property of
each site — the same intents the composer call sites resolve for the
two features (series consistency: ``ANALYSE`` +
``context_mode="series_consistency"``; band summary: ``SUMMARIZE``).

Scope note (audit correction, Task 6c precedent): the plan's "series (2)"
listed voice + consistency, but the voice path already resolves via
``run_author_voice_agent`` (migrated in Task 6a) — the second remaining
series resolution site is the band-summary service, covered here.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from tests.factories import make_chapter, make_novel
from tests.fakes.fake_band_summary_repo import FakeBandSummaryRepository
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.unit.api.series._band_summary_test_helpers import (
    FakeBandSummaryRegistry,
    make_band_summary_config,
    make_band_summary_service,
)
from tests.unit.api.series._series_consistency_test_helpers import (
    FakeSeriesConsistencyRegistry,
    make_config,
    make_service,
    seed_owned_series_with_canon,
)

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


class _PrepareBridgeRegistry:
    """Recording fake exposing the Task-4 assembly point over a domain fake.

    Mirrors the real ``prepare`` contract: exactly one ``get_model``
    resolution, a canned sentinel ``model_settings`` (so pass-through to
    ``agent.run`` is assertable), and the ``usage_limits`` pass-through.
    ``prepare_calls`` records every invocation for wiring assertions.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.prepare_calls: list[dict[str, object]] = []

    async def get_model(
        self, config: Any, *, api_key: str | None = None, base_url: str | None = None
    ) -> Any:
        return await self._inner.get_model(config, api_key=api_key, base_url=base_url)

    async def prepare(
        self,
        config: Any,
        *,
        intent: LLMIntent | None = None,
        usage_limits: Any = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        model = await self._inner.get_model(config, api_key=api_key, base_url=base_url)
        prepared = PreparedModelCall(
            model=model,
            model_settings={"max_tokens": 12_345},
            usage_limits=usage_limits,
        )
        self.prepare_calls.append(
            {
                "config": config,
                "intent": intent,
                "usage_limits": usage_limits,
                "api_key": api_key,
                "base_url": base_url,
                "prepared": prepared,
            }
        )
        return prepared


def _assert_prepare_wiring(
    registry: _PrepareBridgeRegistry,
    config: Any,
    *,
    intent: LLMIntent,
    agent: Any,
) -> None:
    """Assert the full Task-6d wiring contract for one series invocation."""
    assert len(registry.prepare_calls) == 1
    call = registry.prepare_calls[0]
    assert call["config"] is config
    assert call["intent"] is intent
    assert call["api_key"] == _USER_KEY
    assert call["base_url"] == _USER_BASE_URL
    # The coherent triple reaches the agent boundary, and the agent ran.
    prepared = call["prepared"]
    assert isinstance(prepared, PreparedModelCall)
    assert agent.last_model is prepared.model
    assert agent.last_run_kwargs["model_settings"] is prepared.model_settings
    assert agent.last_run_kwargs["usage_limits"] is prepared.usage_limits
    # No run-limit resolver is wired on these series paths (Task 6d
    # concern, same as 6a/6b/6c): the pass-through value is None.
    assert prepared.usage_limits is None
    assert agent.run_count == 1


class TestSeriesConsistencyPrepareWiring:
    """SeriesConsistencyAgent resolves via prepare(ANALYSE) + credentials."""

    async def test_check_novel_resolves_via_prepare_with_analyse_intent(self) -> None:
        config = make_config()
        registry = _PrepareBridgeRegistry(FakeSeriesConsistencyRegistry())
        service, agent, kb_repo, series_repo, novel_repo, chapter_repo = make_service(
            registry=registry,
            config=config,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )
        user_id = uuid4()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )

        await service.check_novel(series_id, novel_id, user_id)

        _assert_prepare_wiring(registry, config, intent=LLMIntent.ANALYSE, agent=agent)


class TestBandSummaryPrepareWiring:
    """BandSummaryAgent resolves via prepare(SUMMARIZE) + credentials."""

    async def test_generate_resolves_via_prepare_with_summarize_intent(self) -> None:
        config = make_band_summary_config()
        registry = _PrepareBridgeRegistry(FakeBandSummaryRegistry())
        novel_id = uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, title="The Forbidden Vale", genre="Fantasy"))
        chapter_repo = FakeChapterRepository()
        chapter_repo.seed(
            make_chapter(novel_id=novel_id, position=1, summary="Hero arrives."),
            make_chapter(novel_id=novel_id, position=2, summary="Secret revealed."),
        )

        service, agent, _ = make_band_summary_service(
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            repo=FakeBandSummaryRepository(),
            registry=registry,
            config=config,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        await service.generate(novel_id)

        _assert_prepare_wiring(registry, config, intent=LLMIntent.SUMMARIZE, agent=agent)
