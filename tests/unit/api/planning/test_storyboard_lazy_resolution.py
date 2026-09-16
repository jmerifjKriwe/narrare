"""Lazy first-use resolve + graceful degradation of StoryboardService
(ADR-086 L21, Pattern M-graceful).

Service-level half of the L21 lazy contract:

- First use (the remap path) runs the per-user PLAN routing cascade
  EXACTLY ONCE, cached and idempotent across entry points (the eager
  factory resolved exactly once per request too).
- The uid-scoped novel guard (``_get_novel`` — same repo, same session
  as the eager factory's wiring-time guard) runs immediately BEFORE the
  first-use resolve (gate-before-resolution ordering, ADR-086 planning
  guard ruling).
- Graceful degradation is service policy (RULE-11 sanctioned graceful
  set): ``ConfigurationError`` (no AI provider) is caught at the remap
  entry, logged (``no_ai_provider_configured`` — the eager factory's
  event, byte-identical), and leaves the triple unset so AI remap
  degrades to the position-ratio heuristic exactly as it did when the
  eager factory swallowed this error at wiring time — WHAT unchanged.
- Non-AI entry points (storyboard view, sync status, outline CRUD)
  never resolve at all (the eager factory resolved for every request).

Mirrors ``tests/unit/api/planning/test_character_arc_lazy_resolution.py``
(ADR-086 L20 convention). Factory-level wiring pins live in
``test_service_factory_wiring.py``.

See:
    ADR-086 — lazy model resolution (L21; Pattern M-graceful)
    docs/superpowers/plans/2026-09-12-adr086-ledger-migration.md §3
    (planning guard note) + §1 (M-graceful)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from narrare_core.shared.errors import ConfigurationError, NotFoundError
from tests.factories import make_chapter_outline
from tests.fakes import FakeChapterRepository, FakeNovelRepository, FakeOutlineRepository
from tests.unit.api.planning._storyboard_test_helpers import (
    _CASCADE_CONFIG,
    make_resolved_model,
)
from tests.unit.api.planning.test_storyboard_ai_remap import _seed_chapters, _seed_novel
from tests.unit.api.planning.test_storyboard_ai_remap_activation import (
    _fake_composer_service,
    _FakeRemapAgent,
    _RecordingModelRegistry,
)

if TYPE_CHECKING:
    from narrare._app.dependencies_services import ModelResolution
    from narrare.planning.service import StoryboardService
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.planning.remap import AIRemapService


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


def _seed_remap_ready(
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
    outline_repo: FakeOutlineRepository,
) -> tuple[UUID, UUID]:
    """Seed a novel + 3 outlined, summarized chapters (AI coverage met)."""

    novel_id, user_id = _seed_novel(novel_repo, story_structure="three_act")
    chapter_ids = _seed_chapters(chapter_repo, novel_id, 3, with_summaries=True)
    for cid in chapter_ids:
        outline_repo.seed(make_chapter_outline(chapter_id=cid, stage_assignment="act-1"))
    return novel_id, user_id


def _make_service(
    resolution: _CountingResolution,
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
    *,
    registry: ModelRegistry | None = None,
    ai_remap_service: AIRemapService | None = None,
) -> StoryboardService:
    """Build a StoryboardService wired with a counting resolution."""
    from narrare.planning.service import StoryboardService

    return StoryboardService(
        outline_repo=FakeOutlineRepository(),
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        ai_remap_service=ai_remap_service,
        model_registry=cast("ModelRegistry | None", registry),
        model_resolution=cast("ModelResolution", resolution),
    )


# ---------------------------------------------------------------------------
# First-use resolve (ADR-086 regression contract #2)
# ---------------------------------------------------------------------------


class TestLazyFirstUse:
    """The remap path resolves exactly once; repeat use is idempotent."""

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First call runs the cascade ONCE and caches the triple; repeat
        calls return without re-running the cascade (ADR-086 contract #2)."""
        from narrare.planning._storyboard_support import StoryboardResolution

        resolution = _CountingResolution(make_resolved_model(api_key="sk-user"))
        support = StoryboardResolution(cast("ModelResolution", resolution))

        await support.ensure_resolved()
        await support.ensure_resolved()

        assert resolution.calls == 1
        assert support.config is _CASCADE_CONFIG
        assert support.api_key == "sk-user"
        assert support.base_url is None

    async def test_entry_point_resolves_exactly_once_across_remap_calls(
        self,
    ) -> None:
        """Preview + confirm on the SAME instance trigger exactly ONE
        cascade run (idempotent across entry points)."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_remap_ready(novel_repo, chapter_repo, FakeOutlineRepository())
        resolution = _CountingResolution(make_resolved_model())
        service = _make_service(
            resolution,
            novel_repo,
            chapter_repo,
            registry=cast("ModelRegistry", _RecordingModelRegistry()),
            ai_remap_service=_fake_composer_service(),
        )

        with patch(
            "narrare_core.agents.summary_agent.ChapterSummaryAgent",
            return_value=_FakeRemapAgent(stage="act-2"),
        ):
            await service.preview_remap(novel_id, "five_act", user_id)
            await service.confirm_remap(novel_id, "five_act", user_id)

        assert resolution.calls == 1

    async def test_non_ai_entry_points_never_resolve(self) -> None:
        """Storyboard view, sync status, and outline CRUD consume no
        resolution — the eager factory resolved for EVERY request; the
        lazy wiring resolves only on the remap path (ADR-086 goal)."""
        novel_repo, chapter_repo, outline_repo = (
            FakeNovelRepository(),
            FakeChapterRepository(),
            FakeOutlineRepository(),
        )
        novel_id, user_id = _seed_remap_ready(novel_repo, chapter_repo, outline_repo)
        resolution = _CountingResolution(make_resolved_model())
        service = _make_service(resolution, novel_repo, chapter_repo)
        chapters = await chapter_repo.list_by_novel(novel_id)

        await service.get_storyboard(novel_id, user_id)
        await service.get_sync_status(novel_id, user_id)
        await service.get_or_create_outline(chapters[0].id, "five_act", user_id, novel_id=novel_id)
        from narrare.planning.schemas import OutlineUpdateRequest

        await service.update_outline(
            chapters[0].id, OutlineUpdateRequest(outline_notes="x"), user_id, novel_id=novel_id
        )

        assert resolution.calls == 0, "non-AI entry points must not resolve"


# ---------------------------------------------------------------------------
# Guard-before-resolution (planning guard ruling)
# ---------------------------------------------------------------------------


class TestGuardPrecedesResolution:
    """The uid-scoped novel guard stays ahead of the first-use resolve."""

    async def test_missing_novel_raises_before_resolution(self) -> None:
        """Missing novel → NotFoundError and the cascade NEVER runs."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        _seed_novel(novel_repo, story_structure="three_act")
        other_novel_id, user_id = uuid4(), uuid4()
        resolution = _CountingResolution(make_resolved_model())
        service = _make_service(resolution, novel_repo, chapter_repo)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.preview_remap(other_novel_id, "five_act", user_id)

        assert resolution.calls == 0, "resolution must not run before the novel guard"

    async def test_ensure_resolved_propagates_configuration_error(self) -> None:
        """``ensure_resolved`` stays honest (RULE-11): the raw
        ``ConfigurationError`` propagates — the swallow is entry-point
        policy (``resolve_graceful``), not resolution state."""
        from narrare.planning._storyboard_support import StoryboardResolution

        resolution = _CountingResolution(
            error=ConfigurationError("no provider", code="NO_AI_PROVIDER")
        )
        support = StoryboardResolution(cast("ModelResolution", resolution))

        with pytest.raises(ConfigurationError):
            await support.ensure_resolved()

        assert support.config is None


# ---------------------------------------------------------------------------
# Graceful degradation (ADR-086 regression contract #3 — graceful variant)
# ---------------------------------------------------------------------------


class TestGracefulDegradation:
    """``ConfigurationError`` degrades to the eager world's heuristic
    outcome — never raised through the remap entry point."""

    _FIVE_ACT_STAGES: ClassVar[set[str]] = {
        "exposition",
        "rising-action",
        "climax",
        "falling-action",
        "resolution",
    }

    async def test_no_provider_degrades_to_heuristic_remap(self) -> None:
        """No AI provider → the eager factory's ``no_ai_provider_configured``
        event is logged and the remap returns heuristic stages — the
        preserved ``model_config=None`` outcome, timing-only moved."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_remap_ready(novel_repo, chapter_repo, FakeOutlineRepository())
        resolution = _CountingResolution(
            error=ConfigurationError("no provider", code="NO_AI_PROVIDER")
        )
        service = _make_service(
            resolution,
            novel_repo,
            chapter_repo,
            registry=cast("ModelRegistry", _RecordingModelRegistry()),
            ai_remap_service=_fake_composer_service(),
        )

        with patch("narrare.planning._storyboard_support.logger") as fake_logger:
            result = await service.preview_remap(novel_id, "five_act", user_id)

        assert resolution.calls == 1
        assert result.confirmed is False
        assert all(item.new_stage in self._FIVE_ACT_STAGES for item in result.remapped)
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
        novel_id, user_id = _seed_remap_ready(novel_repo, chapter_repo, FakeOutlineRepository())
        resolution = _CountingResolution(
            error=ConfigurationError("no provider", code="NO_AI_PROVIDER")
        )
        service = _make_service(
            resolution,
            novel_repo,
            chapter_repo,
            registry=cast("ModelRegistry", _RecordingModelRegistry()),
            ai_remap_service=_fake_composer_service(),
        )

        for _ in range(2):
            await service.preview_remap(novel_id, "five_act", user_id)

        assert resolution.calls == 1, "degraded resolve must not be retried"

    async def test_resolved_triple_reaches_prepare(self) -> None:
        """The resolved triple flows into ``registry.prepare`` verbatim —
        the eager factory's WHAT (config + credentials), timing-only
        moved."""
        novel_repo, chapter_repo = FakeNovelRepository(), FakeChapterRepository()
        novel_id, user_id = _seed_remap_ready(novel_repo, chapter_repo, FakeOutlineRepository())
        registry = _RecordingModelRegistry()
        resolution = _CountingResolution(make_resolved_model(api_key="sk-user"))
        service = _make_service(
            resolution,
            novel_repo,
            chapter_repo,
            registry=cast("ModelRegistry", registry),
            ai_remap_service=_fake_composer_service(),
        )

        with patch(
            "narrare_core.agents.summary_agent.ChapterSummaryAgent",
            return_value=_FakeRemapAgent(stage="act-2"),
        ):
            await service.preview_remap(novel_id, "five_act", user_id)

        assert len(registry.prepare_calls) == 1
        call = registry.prepare_calls[0]
        assert call["config"] is _CASCADE_CONFIG
        assert call["api_key"] == "sk-user"
        assert call["base_url"] is None
