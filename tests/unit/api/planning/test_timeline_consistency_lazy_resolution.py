"""Lazy first-use resolve + graceful degradation of TimelineConsistencyService
(ADR-086 L23, Pattern M-graceful).

Service-level half of the L23 lazy contract:

- First use (``check_consistency``) runs the per-user PLAN routing
  cascade EXACTLY ONCE and caches the resolved config — repeat calls
  are idempotent (the eager factory resolved exactly once per request).
- The uid-scoped novel guard (the service's existing ``get_by_id``
  check — same repo, same session as the eager factory's wiring-time
  guard) runs immediately BEFORE the first-use resolve
  (gate-before-resolution ordering, ADR-086 planning guard ruling).
- Graceful degradation is service policy (RULE-11 sanctioned graceful
  set): ``ConfigurationError`` (no AI provider) is caught at the entry
  point, logged (``no_ai_provider_configured`` — the eager factory's
  event, byte-identical), and leaves the config unset so the LLM checks
  skip and the preserved deterministic-only outcome returns exactly as
  it did when the eager factory swallowed this error at wiring time —
  WHAT unchanged.
- The non-AI entry point (``get_character_ages``) never resolves at
  all (the eager factory resolved for every request).

Mirrors ``tests/unit/api/planning/test_timeline_analysis_lazy_resolution.py``
(ADR-086 L22 convention, itself mirroring L20/L21). Factory-level wiring
pins live in ``test_timeline_factory_wiring.py``.

See:
    ADR-086 — lazy model resolution (L23; Pattern M-graceful)
    docs/superpowers/plans/2026-09-12-adr086-ledger-migration.md §3
    (planning guard note) + §1 (M-graceful)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from narrare_core.shared.errors import ConfigurationError, NotFoundError
from tests.fakes import FakeNovelRepository
from tests.unit.planning._timeline_test_helpers import (
    _CASCADE_CONFIG,
    FakeComposer,
    NoProviderResolution,
    make_resolved_model,
)

if TYPE_CHECKING:
    from narrare._app.dependencies_services import ModelResolution
    from narrare.planning.timeline_consistency_service import TimelineConsistencyService
    from narrare.planning.timeline_repository import TimelineEventRepository
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


class _EmptyEventRepo:
    """Minimal fake event repo — a novel with no timeline events yet."""

    async def list_by_novel(self, _novel_id: object) -> list[object]:
        return []


def _make_service(
    resolution: _CountingResolution | NoProviderResolution,
    novel_repo: FakeNovelRepository,
    *,
    registry: ModelRegistry | None = None,
    composer: PromptComposer | None = None,
) -> TimelineConsistencyService:
    """Build a TimelineConsistencyService wired with the given resolution."""
    from narrare.planning.character_age_service import CharacterAgeService
    from narrare.planning.timeline_consistency_service import TimelineConsistencyService

    return TimelineConsistencyService(
        event_repo=cast("TimelineEventRepository", _EmptyEventRepo()),
        novel_repo=novel_repo,
        character_age_service=CharacterAgeService(novel_repo=novel_repo, kb_repo=None),
        model_registry=cast("ModelRegistry | None", registry),
        model_resolution=cast("ModelResolution", resolution),
        composer=cast("PromptComposer | None", composer),
    )


# ---------------------------------------------------------------------------
# First-use resolve (ADR-086 regression contract #2)
# ---------------------------------------------------------------------------


class TestLazyFirstUse:
    """``check_consistency`` resolves exactly once; repeat use is idempotent."""

    async def test_check_consistency_resolves_once_and_caches_config(self) -> None:
        """One entry-point call triggers exactly ONE cascade run and
        caches the resolved config (the eager factory also resolved
        exactly once per request)."""
        novel_repo = FakeNovelRepository()
        novel_id, user_id = _seed(novel_repo)
        resolution = _CountingResolution(make_resolved_model())
        service = _make_service(
            resolution,
            novel_repo,
            registry=cast("ModelRegistry", object()),
            composer=FakeComposer(),
        )

        result = await service.check_consistency(novel_id, user_id)

        assert resolution.calls == 1
        assert service._config is _CASCADE_CONFIG
        assert [i for i in result.issues if i.source == "llm"] == []

    async def test_character_ages_entry_point_never_resolves(self) -> None:
        """``get_character_ages`` consumes no resolution — the eager
        factory resolved for EVERY request; the lazy wiring resolves only
        on the AI path (ADR-086 goal)."""
        novel_repo = FakeNovelRepository()
        novel_id, user_id = _seed(novel_repo)
        resolution = _CountingResolution(make_resolved_model())
        service = _make_service(resolution, novel_repo)

        report = await service.get_character_ages(novel_id, user_id)

        assert resolution.calls == 0, "non-AI entry points must not resolve"
        assert report.characters == []


# ---------------------------------------------------------------------------
# Guard-before-resolution (planning guard ruling)
# ---------------------------------------------------------------------------


class TestGuardPrecedesResolution:
    """The uid-scoped novel guard stays ahead of the first-use resolve."""

    async def test_missing_novel_raises_before_resolution(self) -> None:
        """Missing novel → NotFoundError and the cascade NEVER runs."""
        novel_repo = FakeNovelRepository()
        _seed(novel_repo)
        other_novel_id, user_id = uuid4(), uuid4()
        resolution = _CountingResolution(make_resolved_model())
        service = _make_service(resolution, novel_repo)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.check_consistency(other_novel_id, user_id)

        assert resolution.calls == 0, "resolution must not run before the novel guard"


# ---------------------------------------------------------------------------
# Graceful degradation (ADR-086 regression contract #3 — graceful variant)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """``ConfigurationError`` degrades to the eager world's outcome —
    deterministic-only checking, never a raised wiring-time event."""

    async def test_no_provider_degrades_to_deterministic_only(self) -> None:
        """No AI provider → the eager factory's ``no_ai_provider_configured``
        event is logged and the check returns the deterministic-only
        report exactly as it did when the eager factory swallowed this
        error at wiring time — WHAT unchanged, timing-only moved."""
        novel_repo = FakeNovelRepository()
        novel_id, user_id = _seed(novel_repo)
        resolution = _CountingResolution(
            error=ConfigurationError("no provider", code="NO_AI_PROVIDER")
        )
        service = _make_service(
            resolution,
            novel_repo,
            registry=cast("ModelRegistry", object()),
            composer=FakeComposer(),
        )

        with patch("narrare.planning.timeline_consistency_service.logger") as fake_logger:
            result = await service.check_consistency(novel_id, user_id)

        assert resolution.calls == 1
        assert [i for i in result.issues if i.source == "llm"] == []
        assert result.deterministic_pass is True
        fake_logger.info.assert_called_once()
        event = fake_logger.info.call_args.args[0]
        assert event == "no_ai_provider_configured", (
            "degradation must log the eager factory's event verbatim"
        )

    async def test_degraded_resolve_not_retried_on_second_call(self) -> None:
        """A failed resolve is cached as attempted — the cascade runs at
        most once per instance even across repeated entry-point calls
        (the eager world also resolved exactly once per request)."""
        novel_repo = FakeNovelRepository()
        novel_id, user_id = _seed(novel_repo)
        resolution = _CountingResolution(
            error=ConfigurationError("no provider", code="NO_AI_PROVIDER")
        )
        service = _make_service(resolution, novel_repo)

        for _ in range(2):
            await service.check_consistency(novel_id, user_id)

        assert resolution.calls == 1, "degraded resolve must not be retried"


def _seed(novel_repo: FakeNovelRepository) -> tuple[UUID, UUID]:
    """Seed one owned novel; returns (novel_id, user_id)."""
    from tests.unit.api.planning.test_storyboard_ai_remap import _seed_novel

    return _seed_novel(novel_repo)
