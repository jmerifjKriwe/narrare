"""Lazy first-use resolve + graceful degradation of TimelineExtractionService
(ADR-086 L24, Pattern M-graceful).

Service-level half of the L24 lazy contract:

- First use (``stream_extraction`` — the only entry point; the REST
  variant delegates to it) runs the per-user PLAN routing cascade
  EXACTLY ONCE and caches the resolved triple (config, api key,
  base url) — repeat calls are idempotent (the eager factory resolved
  exactly once per request too). Unlike L22, the extraction service has
  NO non-AI entry point: both access patterns consume the resolution,
  so every entry resolves at most once.
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

Mirrors ``tests/unit/api/planning/test_timeline_analysis_lazy_resolution.py``
(ADR-086 L22 convention, itself mirroring L20/L21). The factory-level
construction-neutrality pin for this slice lives in
``TestFactoryConstructionNeutrality`` below.

See:
    ADR-086 — lazy model resolution (L24; Pattern M-graceful)
    docs/superpowers/plans/2026-09-12-adr086-ledger-migration.md §3
    (planning guard note) + §1 (M-graceful)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from narrare._app.dependencies_services import LazyModelResolution
from narrare_core.shared.errors import ConfigurationError, NotFoundError
from tests.fakes import FakeChapterRepository, FakeNovelRepository
from tests.unit.api.planning.test_storyboard_ai_remap import _seed_chapters, _seed_novel
from tests.unit.api.planning.test_storyboard_ai_remap_activation import _RecordingModelRegistry
from tests.unit.planning._timeline_test_helpers import (
    NoProviderResolution,
    make_resolved_model,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare._app.dependencies_services import ModelResolution
    from narrare.planning.timeline_extraction_service import TimelineExtractionService
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


def _make_service(
    resolution: _CountingResolution | NoProviderResolution,
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
    *,
    registry: ModelRegistry | None = None,
) -> TimelineExtractionService:
    """Build a TimelineExtractionService wired with the given resolution."""
    from narrare.planning.timeline_extraction_service import TimelineExtractionService
    from tests.unit.api.planning._timeline_extraction_test_helpers import FakeComposer

    return TimelineExtractionService(
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        model_registry=cast("ModelRegistry", registry or _RecordingModelRegistry()),
        model_resolution=cast("ModelResolution", resolution),
        composer=cast("PromptComposer", FakeComposer()),
    )


async def _stream(
    service: TimelineExtractionService,
    novel_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[object]:
    """Collect the extraction stream (chapter_ids=None → all chapters)."""
    return [e async for e in service.stream_extraction(novel_id, user_id, None)]


# ---------------------------------------------------------------------------
# First-use resolve (ADR-086 regression contract #2)
# ---------------------------------------------------------------------------


class TestLazyFirstUse:
    """``stream_extraction`` resolves exactly once; repeat use is idempotent."""

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First call runs the cascade ONCE and caches the triple; repeat
        calls return without re-running the cascade (ADR-086 contract #2)."""
        resolution = _CountingResolution(make_resolved_model(api_key="sk-user"))
        service = _make_service(resolution, FakeNovelRepository(), FakeChapterRepository())

        await service.ensure_resolved()
        await service.ensure_resolved()

        assert resolution.calls == 1
        assert service._config is not None
        assert service._api_key == "sk-user"
        assert service._base_url is None

    async def test_stream_extraction_resolves_exactly_once(self) -> None:
        """One full stream (REST variant included via delegation) triggers
        exactly ONE cascade run (the eager factory also resolved exactly
        once per request)."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 1, with_summaries=True)
        resolution = _CountingResolution(make_resolved_model())
        service = _make_service(resolution, novel_repo, chapter_repo)

        from tests.unit.api.planning._timeline_extraction_test_helpers import (
            FakeComposedInvocation,
            make_agent_output,
        )

        agent = AsyncMock(run=AsyncMock(return_value=make_agent_output()))
        with (
            patch(
                "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent",
                return_value=agent,
            ),
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ),
        ):
            await _stream(service, novel_id, user_id)

        assert resolution.calls == 1


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
            await _stream(service, other_novel_id, user_id)

        assert resolution.calls == 0, "resolution must not run before the novel guard"


# ---------------------------------------------------------------------------
# Graceful degradation (ADR-086 regression contract #3 — graceful variant)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """``ConfigurationError`` degrades to the eager world's outcome —
    the preserved ``NO_AI_PROVIDER`` raise, never a wiring-time event."""

    async def test_no_provider_degrades_to_preserved_no_provider_outcome(self) -> None:
        """No AI provider → the eager factory's ``no_ai_provider_configured``
        event is logged and the stream raises the SAME ``ConfigurationError``
        it raised when the eager factory swallowed this error at wiring
        time — WHAT unchanged, timing-only moved."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 1, with_summaries=True)
        resolution = _CountingResolution(
            error=ConfigurationError("no provider", code="NO_AI_PROVIDER")
        )
        service = _make_service(resolution, novel_repo, chapter_repo)

        with (
            patch("narrare.planning.timeline_extraction_service.logger") as fake_logger,
            pytest.raises(ConfigurationError, match="Configure one in Settings"),
        ):
            await _stream(service, novel_id, user_id)

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
        _seed_chapters(chapter_repo, novel_id, 1, with_summaries=True)
        resolution = _CountingResolution(
            error=ConfigurationError("no provider", code="NO_AI_PROVIDER")
        )
        service = _make_service(resolution, novel_repo, chapter_repo)

        for _ in range(2):
            with pytest.raises(ConfigurationError):
                await _stream(service, novel_id, user_id)

        assert resolution.calls == 1, "degraded resolve must not be retried"

    async def test_resolved_triple_reaches_prepare(self) -> None:
        """The resolved triple flows into ``registry.prepare`` verbatim —
        the eager factory's WHAT (config + credentials), timing-only
        moved."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_novel(novel_repo)
        _seed_chapters(chapter_repo, novel_id, 1, with_summaries=True)
        registry = _RecordingModelRegistry()
        resolved_model = make_resolved_model(api_key="sk-user")
        resolution = _CountingResolution(resolved_model)
        service = _make_service(resolution, novel_repo, chapter_repo, registry=registry)

        from tests.unit.api.planning._timeline_extraction_test_helpers import (
            FakeComposedInvocation,
            make_agent_output,
        )

        agent = AsyncMock(run=AsyncMock(return_value=make_agent_output()))
        with (
            patch(
                "narrare_core.agents.temporal_extraction_agent.TemporalExtractionAgent",
                return_value=agent,
            ),
            patch("narrare_core.agents.temporal_extraction_agent.TemporalExtractionDeps"),
            patch(
                "narrare_core.ai_invocation.compose_invocation",
                new=AsyncMock(return_value=FakeComposedInvocation()),
            ),
        ):
            await _stream(service, novel_id, user_id)

        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is resolved_model.config
        assert call["api_key"] == "sk-user"
        assert call["base_url"] is None


# ---------------------------------------------------------------------------
# Factory construction neutrality (ADR-086 regression contract #1)
# ---------------------------------------------------------------------------


class TestFactoryConstructionNeutrality:
    """``get_timeline_extraction_service`` wires lazily — construction
    performs NO routing work (the eager factory resolved at wiring time)."""

    async def test_factory_builds_service_without_resolving(self) -> None:
        """The factory returns a service whose cascade has NOT run — the
        per-user PLAN resolve happens on the service's first AI use."""
        from narrare.planning._timeline_extraction_factory import (
            get_timeline_extraction_service,
        )

        resolver = AsyncMock(resolve=AsyncMock(return_value=make_resolved_model()))
        with (
            patch(
                "narrare.planning._timeline_extraction_factory.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare.planning._timeline_extraction_factory.get_model_registry",
            ) as _registry_dep,
            patch("narrare.planning._timeline_extraction_factory.get_composer"),
            patch(
                "narrare.planning._timeline_extraction_factory.get_invocation_pipeline",
            ),
        ):
            service = await get_timeline_extraction_service(
                session=cast("AsyncSession", AsyncMock()),
                user_id=str(uuid4()),
                novel_id=uuid4(),
            )

        assert resolver.resolve.await_count == 0, "factory must not resolve at wiring time"
        assert service._resolve_attempted is False
        assert service._config is None
        assert isinstance(service._model_resolution, LazyModelResolution), (
            "the per-user PLAN cascade must be wired as a LazyModelResolution"
        )
