"""Lazy model-resolution semantics for SeriesVoiceDriftService (ADR-086 L29).

The factory (``series/dependencies_voice_drift.py::
get_series_voice_drift_service``) wires a ``LazyModelResolution``; this file
pins the SERVICE-side lazy contract:

- no resolution at construction,
- exactly one resolve at first use, idempotent afterwards,
- ``ConfigurationError`` propagates un-swallowed from the entry point
  (RULE-11 — AI-mandatory endpoint), with the ownership gates running
  FIRST (gates stay ahead of resolution),
- the resolved triple reaches ``ModelRegistry.prepare``/``get_model``
  unchanged — the eager factory applied no sampling overrides, so none
  appear (WHAT unchanged, only WHEN),
- the graceful no-profile degradation is DOWNSTREAM of resolution: an
  unconfigured provider stays a loud 400-equivalent even when the check
  would degrade to a ``no_profile`` result (the eager factory resolved
  before the early exit too — timing-only migration).

Mirrors ``tests/unit/api/series/test_series_consistency_service_lazy_resolution.py``
(ADR-086 L26 D-family precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
from narrare.series.series_voice_drift_service import SeriesVoiceDriftService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError, ForbiddenError
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

from ._series_voice_drift_test_helpers import (
    make_author_profile,
    make_composer,
    make_config,
    make_drift_result,
    patch_mode1,
    seed_owned_series,
    seed_series_voice,
)

if TYPE_CHECKING:
    from narrare._app.dependencies_services import ModelResolution
    from narrare_core.llm.gateway import ModelRegistry


class _StopResolution(BaseException):
    """Sentinel raised after get_model recorded its call (short-circuits run).

    ``BaseException`` (not ``Exception``) so the services' broad
    ``except Exception`` error wrappers (RULE-11) cannot swallow it into a
    ``WritingError``.
    """


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches.

    Exposes the service-level lazy seam (ADR-086): the service must call
    ``resolve()`` exactly once (first use), never at construction.
    """

    def __init__(self, model: ResolvedModel) -> None:
        self._model = model
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        return self._model


class _RaisingResolution:
    """Fake ModelResolution — the cascade finds no configured provider."""

    async def resolve(self) -> ResolvedModel:
        raise ConfigurationError(
            "No AI provider configured.",
            code="NO_AI_PROVIDER",
        )


class _RecordingRegistry:
    """Fake ModelRegistry — records ``get_model`` calls for assertions."""

    def __init__(self, stop_after_record: BaseException | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._stop = stop_after_record

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: object = None,
    ) -> object:
        self.calls.append({"config": config, "api_key": api_key, "base_url": base_url})
        if self._stop is not None:
            raise self._stop
        return MagicMock(spec=object)

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        """Resolution flows through prepare → get_model (Task-6a shape)."""
        from types import SimpleNamespace

        return SimpleNamespace(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )


def _resolved_model(
    config: ResolvedModelConfig | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=config or make_config(),
        api_key=api_key,
        base_url=base_url,
        source="unit-test",
    )


def _make_service(
    model_resolution: ModelResolution,
    registry: _RecordingRegistry | None = None,
) -> tuple[
    SeriesVoiceDriftService, FakeSeriesRepository, FakeNovelRepository, FakeChapterRepository
]:
    """Build an UNSEEDED SeriesVoiceDriftService with the lazy seam injected.

    Nodes seed their own series/novel/chapters via :func:`seed_owned_series`
    (keeping the ``user_id`` handle, mirroring ``test_series_voice_drift_service``)
    and the profile via :func:`seed_series_voice`. Returns
    ``(service, series_repo, novel_repo, chapter_repo)``.
    """
    series_repo = FakeSeriesRepository()
    novel_repo = FakeNovelRepository()
    chapter_repo = FakeChapterRepository()

    service = SeriesVoiceDriftService(
        series_repo=cast("Any", series_repo),
        novel_repo=cast("Any", novel_repo),
        chapter_repo=cast("Any", chapter_repo),
        model_registry=cast("ModelRegistry", registry or _RecordingRegistry()),
        model_resolution=model_resolution,
        composer=cast("Any", make_composer()),
    )
    return service, series_repo, novel_repo, chapter_repo


class TestLazyResolutionContract:
    """ADR-086 lazy resolution at the SeriesVoiceDriftService boundary."""

    async def test_no_resolution_at_construction(self) -> None:
        """Construction must not touch the routing cascade."""
        counting = _CountingResolution(_resolved_model())

        _make_service(counting)

        assert counting.calls == 0

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First use resolves exactly once; repeat calls hit the cache."""
        counting = _CountingResolution(_resolved_model())
        service, *_repos = _make_service(counting)

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert counting.calls == 1
        assert first is second

    async def test_check_resolves_exactly_once(self) -> None:
        """The entry point is the first-use seam — one resolve per check."""
        counting = _CountingResolution(_resolved_model())
        registry = _RecordingRegistry()
        service, series_repo, novel_repo, chapter_repo = _make_service(counting, registry)
        user_id = uuid4()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )
        await seed_series_voice(series_repo, series_id, make_author_profile())

        with patch_mode1() as (mock_agent_cls, _mock_compose):
            mock_agent = MagicMock(spec=["run"])
            mock_agent.run = AsyncMock(return_value=make_drift_result())
            mock_agent_cls.return_value = mock_agent

            await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())

        assert counting.calls == 1

    async def test_resolver_configuration_error_propagates_un_swallowed(self) -> None:
        """RULE-11 / ADR-086: the cascade's ``ConfigurationError``
        (unconfigured provider) propagates from the entry point — the
        service never swallows it (AI-mandatory endpoint). The ownership
        gates run FIRST and pass (seeded repos), so the error comes from
        resolution, proving gates stay ahead of resolution."""
        service, series_repo, novel_repo, chapter_repo = _make_service(_RaisingResolution())
        user_id = uuid4()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )

        with pytest.raises(ConfigurationError):
            await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())

    async def test_ownership_gates_stay_ahead_of_resolution(self) -> None:
        """A non-owned series is rejected with ``ForbiddenError`` and the
        routing cascade is NEVER invoked — the gates precede resolution
        (eager-world precedence preserved; MUST-NOT-change list)."""
        counting = _CountingResolution(_resolved_model())
        service, series_repo, novel_repo, chapter_repo = _make_service(counting)
        user_id = uuid4()
        series_id, _novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )

        with pytest.raises(ForbiddenError):
            await service.check(series_id, uuid4(), user_id, AuthorVoiceDriftRequest())

        assert counting.calls == 0

    async def test_unconfigured_provider_stays_loud_on_graceful_degradation_path(
        self,
    ) -> None:
        """The no-profile early exit is DOWNSTREAM of resolution: with an
        unconfigured provider the entry point raises ``ConfigurationError``
        instead of returning the graceful ``no_profile`` result — the eager
        factory also failed before the early exit could run (timing-only
        invariant: WHAT is unchanged, only WHEN)."""
        service, series_repo, novel_repo, chapter_repo = _make_service(_RaisingResolution())
        user_id = uuid4()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )
        # No seed_series_voice → the graceful no_profile path would trigger
        # IF resolution were deferred past it.

        with pytest.raises(ConfigurationError):
            await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())

    async def test_resolved_triple_flows_into_get_model_unchanged(self) -> None:
        """Timing-only invariant: the eager factory passed
        ``resolved.config`` + credentials into the drift pipeline
        verbatim — the lazy service passes the SAME values (no sampling
        overrides exist for series voice-drift's VOICE resolve)."""
        resolved_config = ResolvedModelConfig(
            provider_name="zai",
            model_id="glm-4.7",
            temperature=0.7,
            max_tokens=4096,
        )
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service, series_repo, novel_repo, chapter_repo = _make_service(
            _CountingResolution(_resolved_model(resolved_config, api_key="sk-user-key")),
            registry,
        )
        user_id = uuid4()
        series_id, novel_id = seed_owned_series(
            series_repo, novel_repo, chapter_repo, user_id=user_id
        )
        await seed_series_voice(series_repo, series_id, make_author_profile())

        # get_model raises the sentinel through the (real) shared pipeline —
        # proving the credentials travel resolution → service → get_model.
        with patch_mode1(), pytest.raises(_StopResolution):
            await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())

        assert registry.calls == [
            {"config": resolved_config, "api_key": "sk-user-key", "base_url": None}
        ]
