"""Lazy model-resolution semantics for SeriesVoiceService (ADR-086 L28).

The factory (``series/dependencies_voice.py::get_series_voice_service``)
wires a ``LazyModelResolution``; this file pins the SERVICE-side lazy
contract:

- no resolution at construction,
- exactly one resolve at first use, idempotent afterwards,
- ``ConfigurationError`` propagates un-swallowed from the entry point
  (RULE-11 — AI-mandatory endpoint), with the ownership gates running
  FIRST (gates stay ahead of resolution),
- the resolved triple reaches ``ModelRegistry.prepare`` unchanged — the
  eager factory applied no sampling overrides, so none appear (WHAT
  unchanged, only WHEN),
- the graceful no-chapters early exit is DOWNSTREAM of resolution: an
  unconfigured provider stays a loud 400-equivalent even when the profile
  would fail fast below (the eager factory resolved before the early exit
  too — timing-only migration).

Mirrors ``tests/unit/api/series/test_series_consistency_service_lazy_resolution.py``
(ADR-086 L26 precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest

from narrare.series.series_voice_service import SeriesVoiceService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError, ForbiddenError
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

from ._series_voice_drift_test_helpers import seed_owned_series
from ._series_voice_test_helpers import (
    _FakeComposer,
    _FakeModelRegistry,
    patch_author_voice_pipeline,
)

if TYPE_CHECKING:
    from narrare._app.dependencies_services import ModelResolution


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


def _resolved_model(
    config: ResolvedModelConfig | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=config or ResolvedModelConfig(provider_name="test", model_id="test-model"),
        api_key=api_key,
        base_url=base_url,
        source="unit-test",
    )


def _make_service(
    model_resolution: ModelResolution,
    registry: _FakeModelRegistry | None = None,
    *,
    seed: bool = True,
    chapter_count: int = 3,
) -> tuple[
    SeriesVoiceService,
    FakeSeriesRepository,
    FakeNovelRepository,
    FakeChapterRepository,
    UUID,
    UUID,
    UUID,
]:
    """Build a SeriesVoiceService with the lazy seam injected.

    When ``seed`` is True, an owned series + one member novel (+ prose
    chapters) are seeded so ``profile_from_novel`` flows past the gates
    into the invocation. Returns
    ``(service, series_repo, novel_repo, chapter_repo, series_id,
    novel_id, user_id)``.
    """
    series_repo = FakeSeriesRepository()
    novel_repo = FakeNovelRepository()
    chapter_repo = FakeChapterRepository()

    user_id = uuid4()
    if seed:
        series_id, novel_id = seed_owned_series(
            series_repo,
            novel_repo,
            chapter_repo,
            user_id=user_id,
            chapter_count=chapter_count,
        )
    else:
        series_id, novel_id = uuid4(), uuid4()

    service = SeriesVoiceService(
        series_repo=cast("Any", series_repo),
        novel_repo=cast("Any", novel_repo),
        chapter_repo=cast("Any", chapter_repo),
        model_registry=cast("Any", registry or _FakeModelRegistry()),
        model_resolution=model_resolution,
        composer=cast("Any", _FakeComposer()),
    )
    return service, series_repo, novel_repo, chapter_repo, series_id, novel_id, user_id


class TestLazyResolutionContract:
    """ADR-086 lazy resolution at the SeriesVoiceService boundary."""

    async def test_no_resolution_at_construction(self) -> None:
        """Construction must not touch the routing cascade."""
        counting = _CountingResolution(_resolved_model())

        _make_service(counting)

        assert counting.calls == 0

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First use resolves exactly once; repeat calls hit the cache."""
        counting = _CountingResolution(_resolved_model())
        service = _make_service(counting)[0]

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert counting.calls == 1
        assert first is second

    async def test_profile_from_novel_resolves_exactly_once(self) -> None:
        """The entry point is the first-use seam — one resolve per profile."""
        counting = _CountingResolution(_resolved_model())
        service, _sr, _nr, _cr, series_id, novel_id, user_id = _make_service(counting)

        with patch_author_voice_pipeline():
            await service.profile_from_novel(series_id, novel_id, user_id)

        assert counting.calls == 1

    async def test_resolver_configuration_error_propagates_un_swallowed(self) -> None:
        """RULE-11 / ADR-086: the cascade's ``ConfigurationError``
        (unconfigured provider) propagates from the entry point — the
        service never swallows it (AI-mandatory endpoint). The ownership
        gates run FIRST and pass (seeded repos), so the error comes from
        resolution, proving gates stay ahead of resolution."""
        service, _sr, _nr, _cr, series_id, novel_id, user_id = _make_service(_RaisingResolution())

        with pytest.raises(ConfigurationError):
            await service.profile_from_novel(series_id, novel_id, user_id)

    async def test_ownership_gates_stay_ahead_of_resolution(self) -> None:
        """A non-owned series is rejected with ``ForbiddenError`` and the
        routing cascade is NEVER invoked — the gates precede resolution
        (eager-world precedence preserved; MUST-NOT-change list)."""
        counting = _CountingResolution(_resolved_model())
        service, _sr, _nr, _cr, _series_id, novel_id, _user_id = _make_service(counting)

        with pytest.raises(ForbiddenError):
            await service.profile_from_novel(uuid4(), novel_id, uuid4())

        assert counting.calls == 0

    async def test_unconfigured_provider_stays_loud_on_graceful_degradation_path(
        self,
    ) -> None:
        """The no-chapters early exit is DOWNSTREAM of resolution: with an
        unconfigured provider the entry point raises ``ConfigurationError``
        instead of the ``ValidationError`` fail-fast — the eager factory
        also failed before the early exit could run (timing-only
        invariant: WHAT is unchanged, only WHEN)."""
        service, _sr, _nr, _cr, series_id, novel_id, user_id = _make_service(
            _RaisingResolution(), chapter_count=0
        )

        with pytest.raises(ConfigurationError):
            await service.profile_from_novel(series_id, novel_id, user_id)

    async def test_resolved_triple_flows_into_prepare_unchanged(self) -> None:
        """Timing-only invariant: the eager factory passed
        ``resolved.config`` + credentials into the invocation assembly
        verbatim — the lazy service passes the SAME values (no sampling
        overrides exist for series voice's VOICE resolve)."""
        resolved_config = ResolvedModelConfig(
            provider_name="zai",
            model_id="glm-4.7",
            temperature=0.7,
            max_tokens=4096,
        )
        registry = _FakeModelRegistry()
        counting = _CountingResolution(
            _resolved_model(
                resolved_config, api_key="sk-user-key", base_url="https://user.example/v1"
            )
        )
        service, _sr, _nr, _cr, series_id, novel_id, user_id = _make_service(
            counting, registry=registry
        )

        with patch_author_voice_pipeline():
            await service.profile_from_novel(series_id, novel_id, user_id)

        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is resolved_config
        assert call["api_key"] == "sk-user-key"
        assert call["base_url"] == "https://user.example/v1"
        assert cast("Any", call["intent"]).name == "VOICE"
