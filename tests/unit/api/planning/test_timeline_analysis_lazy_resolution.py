"""Lazy first-use resolve + graceful degradation of TimelineAnalysisService
(ADR-086 L22, Pattern M-graceful).

Service-level half of the L22 lazy contract:

- First use (``generate_timeline``) runs the per-user PLAN routing
  cascade EXACTLY ONCE and caches the resolved triple (config, api key,
  base url) — repeat calls are idempotent (the eager factory resolved
  exactly once per request too).
- The uid-scoped novel guard (the service's existing ``get_by_id``
  check — same repo, same session as the eager factory's wiring-time
  guard) runs immediately BEFORE the first-use resolve
  (gate-before-resolution ordering, ADR-086 planning guard ruling).
- Graceful degradation is service policy (RULE-11 sanctioned graceful
  set): ``ConfigurationError`` (no AI provider) is caught at the entry
  point, logged (``no_ai_provider_configured`` — the eager factory's
  event, byte-identical), and leaves the triple unset so the preserved
  ``NO_AI_PROVIDER`` outcome fires exactly as it did when the eager
  factory swallowed this error at wiring time — WHAT unchanged.
- The non-AI entry point (``confirm_extracted_event``) never resolves
  at all (the eager factory resolved for every request).

Mirrors ``tests/unit/api/planning/test_storyboard_lazy_resolution.py``
(ADR-086 L21 convention, itself mirroring L20). Factory-level wiring
pins live in ``test_timeline_factory_wiring.py``.

See:
    ADR-086 — lazy model resolution (L22; Pattern M-graceful)
    docs/superpowers/plans/2026-09-12-adr086-ledger-migration.md §3
    (planning guard note) + §1 (M-graceful)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import patch
from uuid import uuid4

import pytest

from narrare_core.shared.errors import ConfigurationError, NotFoundError
from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api.planning.test_storyboard_ai_remap import _seed_chapters, _seed_novel
from tests.unit.api.planning.test_storyboard_ai_remap_activation import _RecordingModelRegistry
from tests.unit.planning._extraction_confirm_helpers import make_event
from tests.unit.planning._timeline_test_helpers import (
    _CASCADE_CONFIG,
    FakeComposer,
    NoProviderResolution,
    make_mock_agent,
    make_resolved_model,
)

if TYPE_CHECKING:
    from narrare._app.dependencies_services import ModelResolution
    from narrare.planning.timeline_analysis_service import TimelineAnalysisService
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches."""

    def __init__(self, model: object | None = None, error: Exception | None = None) -> None:
        self._model = model
        self._error = error
        self.calls = 0

    async def resolve(self) -> object:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._model


class _RecordingEventRepo:
    """Minimal fake event repo — records create(); confirm path only."""

    def __init__(self) -> None:
        self.created = 0

    async def create(self, **_kw: object) -> object:
        self.created += 1
        return make_event()


def _make_service(
    resolution: _CountingResolution | NoProviderResolution,
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
    *,
    registry: ModelRegistry | None = None,
    composer: PromptComposer | None = None,
) -> TimelineAnalysisService:
    """Build a TimelineAnalysisService wired with the given resolution."""
    from narrare.planning.timeline_analysis_service import TimelineAnalysisService

    return TimelineAnalysisService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        model_registry=cast("ModelRegistry", registry or _RecordingModelRegistry()),
        model_resolution=cast("ModelResolution", resolution),
        composer=cast("PromptComposer | None", composer or FakeComposer()),
    )


# ---------------------------------------------------------------------------
# First-use resolve (ADR-086 regression contract #2)
# ---------------------------------------------------------------------------


class TestLazyFirstUse:
    """``generate_timeline`` resolves exactly once; repeat use is idempotent."""

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First call runs the cascade ONCE and caches the triple; repeat
        calls return without re-running the cascade (ADR-086 contract #2)."""
        resolution = _CountingResolution(make_resolved_model(api_key="sk-user"))
        service = _make_service(resolution, FakeNovelRepository(), FakeChapterRepository())

        await service.ensure_resolved()
        await service.ensure_resolved()

        assert resolution.calls == 1
        assert service._config is _CASCADE_CONFIG
        assert service._api_key == "sk-user"
        assert service._base_url is None

    async def test_generate_timeline_resolves_exactly_once(self) -> None:
        """One ``generate_timeline`` call triggers exactly ONE cascade run
        (the eager factory also resolved exactly once per request)."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 2, with_summaries=True)
        resolution = _CountingResolution(make_resolved_model())
        service = _make_service(resolution, novel_repo, chapter_repo)

        with patch(
            "narrare_core.agents.timeline_agent.TimelineAgent",
            return_value=make_mock_agent(),
        ):
            await service.generate_timeline(novel_id, user_id)

        assert resolution.calls == 1

    async def test_non_ai_entry_point_never_resolves(self) -> None:
        """``confirm_extracted_event`` consumes no resolution — the eager
        factory resolved for EVERY request; the lazy wiring resolves only
        on the AI path (ADR-086 goal)."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_novel(novel_repo)
        resolution = _CountingResolution(make_resolved_model())
        service = _make_service(resolution, novel_repo, chapter_repo)
        event_repo = _RecordingEventRepo()
        object.__setattr__(service, "_event_repo", event_repo)

        from narrare_core.agents.temporal_extraction_types import ExtractedTemporalExpression

        extracted = ExtractedTemporalExpression(
            expression="three days later",
            event_name="Arrival",
            confidence=0.9,
        )
        await service.confirm_extracted_event(novel_id, user_id, extracted)

        assert resolution.calls == 0, "non-AI entry points must not resolve"


# ---------------------------------------------------------------------------
# Guard-before-resolution (planning guard ruling)
# ---------------------------------------------------------------------------


class TestGuardPrecedesResolution:
    """The uid-scoped novel guard stays ahead of the first-use resolve."""

    async def test_missing_novel_raises_before_resolution(self) -> None:
        """Missing novel → NotFoundError and the cascade NEVER runs."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        _seed_novel(novel_repo)
        other_novel_id, user_id = uuid4(), uuid4()
        resolution = _CountingResolution(make_resolved_model())
        service = _make_service(resolution, novel_repo, chapter_repo)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.generate_timeline(other_novel_id, user_id)

        assert resolution.calls == 0, "resolution must not run before the novel guard"


# ---------------------------------------------------------------------------
# Graceful degradation (ADR-086 regression contract #3 — graceful variant)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """``ConfigurationError`` degrades to the eager world's outcome —
    the preserved ``NO_AI_PROVIDER`` raise, never a wiring-time event."""

    async def test_no_provider_degrades_to_preserved_no_provider_outcome(self) -> None:
        """No AI provider → the eager factory's ``no_ai_provider_configured``
        event is logged and ``generate_timeline`` raises the SAME
        ``ConfigurationError`` it raised when the eager factory swallowed
        this error at wiring time — WHAT unchanged, timing-only moved."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 1, with_summaries=True)
        resolution = _CountingResolution(
            error=ConfigurationError("no provider", code="NO_AI_PROVIDER")
        )
        service = _make_service(resolution, novel_repo, chapter_repo)

        with (
            patch("narrare.planning.timeline_analysis_service.logger") as fake_logger,
            pytest.raises(ConfigurationError, match="No AI provider configured"),
        ):
            await service.generate_timeline(novel_id, user_id)

        assert resolution.calls == 1
        fake_logger.info.assert_called_once()
        event = fake_logger.info.call_args.args[0]
        assert event == "no_ai_provider_configured", (
            "degradation must log the eager factory's event verbatim"
        )

    async def test_degraded_resolve_not_retried_on_second_call(self) -> None:
        """A failed resolve is cached as attempted — the cascade runs at
        most once per instance even across repeated entry-point calls
        (the eager world also resolved exactly once per request)."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_novel(novel_repo)
        resolution = _CountingResolution(
            error=ConfigurationError("no provider", code="NO_AI_PROVIDER")
        )
        service = _make_service(resolution, novel_repo, chapter_repo)

        for _ in range(2):
            with pytest.raises(ConfigurationError):
                await service.generate_timeline(novel_id, user_id)

        assert resolution.calls == 1, "degraded resolve must not be retried"

    async def test_resolved_triple_reaches_prepare(self) -> None:
        """The resolved triple flows into ``registry.prepare`` verbatim —
        the eager factory's WHAT (config + credentials), timing-only
        moved."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 1, with_summaries=True)
        registry = _RecordingModelRegistry()
        resolution = _CountingResolution(make_resolved_model(api_key="sk-user"))
        service = _make_service(resolution, novel_repo, chapter_repo, registry=registry)

        with patch(
            "narrare_core.agents.timeline_agent.TimelineAgent",
            return_value=make_mock_agent(),
        ):
            await service.generate_timeline(novel_id, user_id)

        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is _CASCADE_CONFIG
        assert call["api_key"] == "sk-user"
        assert call["base_url"] is None
