"""Lazy factory wiring + graceful first-use resolve of StorySuggestService
(ADR-086 L34, Pattern M-graceful).

Factory-level + service-level halves of the L34 lazy contract:

- ``get_story_suggest_service`` runs ZERO cascades and issues ZERO novel
  queries at construction time — the eager factory's uid-scoped novel
  guard ran at wiring time; per the ADR-086 planning guard ruling it is
  preserved (not dropped) in the SERVICE's first-use paths: the router's
  pre-stream ``validate_suggest`` seam and the ``suggest`` entry point
  both run it immediately BEFORE the first-use resolve
  (gate-before-resolution ordering).
- First use (``ensure_resolved``) runs the per-user SUGGEST routing
  cascade EXACTLY ONCE, cached and idempotent (eager-world timing also
  resolved exactly once per request).
- Graceful degradation is service policy (RULE-11 sanctioned exception):
  ``ConfigurationError`` (no AI provider) is caught at the first-use
  paths, logged (``no_ai_provider_configured`` — the eager factory's
  event, byte-identical), and leaves the config unset so the preserved
  ``no_model_config`` degraded outcome fires in-band — the eager
  factory's swallow semantics moved, WHAT unchanged (AI-optional
  feature).

Mirrors ``tests/unit/api/planning/test_character_arc_lazy_resolution.py``
(ADR-086 L20 convention).

See:
    ADR-086 — lazy model resolution (L34; Pattern M-graceful)
    docs/superpowers/plans/2026-09-12-adr086-ledger-migration.md §3
    (planning guard note) + §1 (M-graceful)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError, NotFoundError
from tests.unit.api.writing._story_suggest_test_helpers import (
    FakeComposer,
    FakeModelRegistry,
    make_agent_output,
    make_novel,
    make_request,
)

if TYPE_CHECKING:
    from narrare.novels.repository import NovelRepository
    from narrare.writing.story_suggest_service import StorySuggestService
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

_CASCADE_CONFIG = ResolvedModelConfig(
    provider_name="zai",
    model_id="glm-4.7",
    temperature=0.7,
)


class _CountingResolution:
    """Fake ModelResolution — counts resolve() calls, never caches."""

    def __init__(self, model: ResolvedModel | None = None) -> None:
        self._model = model
        self.calls = 0

    async def resolve(self) -> ResolvedModel:
        self.calls += 1
        if self._model is None:
            raise ConfigurationError(
                "No AI provider configured.",
                code="NO_AI_PROVIDER",
            )
        return self._model


def _resolved_model() -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=_CASCADE_CONFIG,
        api_key=None,
        base_url=None,
        source="unit-test",
    )


def _make_service(
    resolution: _CountingResolution,
    novel: object | None,
) -> StorySuggestService:
    """Build a StorySuggestService wired with a counting resolution."""
    from narrare.writing.story_suggest_service import StorySuggestService

    novel_repo = MagicMock(spec=["get_by_id"], get_by_id=AsyncMock(return_value=novel))
    return StorySuggestService(
        novel_repo=cast("NovelRepository", novel_repo),
        model_registry=cast("ModelRegistry", FakeModelRegistry()),
        model_resolution=resolution,
        composer=cast("PromptComposer", FakeComposer()),
    )


async def _run_suggest(service: StorySuggestService) -> None:
    """Consume the full ``suggest`` stream (agent boundary patched out)."""
    request = make_request()
    with (
        patch("narrare_core.agents.story_suggest_agent.StorySuggestAgent") as mock_agent_cls,
        patch("narrare_core.agents.story_suggest_types.StorySuggestDeps"),
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(
                return_value=MagicMock(
                    spec=["composed_prompt"],
                    composed_prompt=MagicMock(spec=["system", "user"], system="SYS", user=""),
                )
            ),
        ),
    ):
        mock_agent_cls.return_value = MagicMock(
            spec=["run"], run=AsyncMock(return_value=make_agent_output())
        )
        async for _event in service.suggest(uuid4(), uuid4(), request):
            pass


# ---------------------------------------------------------------------------
# Factory-level: nothing at construction (ADR-086 regression contract #1)
# ---------------------------------------------------------------------------


class TestLazyFactoryWiring:
    """``get_story_suggest_service`` resolves NOTHING at construction."""

    async def test_no_resolution_at_construction(self) -> None:
        """Factory entry runs ZERO cascades and issues ZERO novel queries.

        The eager factory ran the uid-scoped novel guard + the SUGGEST
        cascade at wiring time; both move to the service's first use
        (guard preserved per the planning guard ruling — asserted at
        service level in ``TestGracefulFirstUse``).
        """
        from narrare.writing.deps_story_suggest import get_story_suggest_service

        fake_resolver = MagicMock(spec=["resolve"])
        fake_resolver.resolve = AsyncMock(return_value=_resolved_model())
        novel_repo = MagicMock(spec=["get_by_id"], get_by_id=AsyncMock(return_value=make_novel()))

        with (
            patch(
                "narrare.writing.deps_story_suggest.get_model_routing_resolver",
                return_value=fake_resolver,
            ),
            patch(
                "narrare.writing.deps_story_suggest.get_model_registry",
                return_value=MagicMock(spec=["prepare"]),
            ),
            patch(
                "narrare.writing.deps_story_suggest.get_composer",
                return_value=MagicMock(spec=["build"]),
            ),
            patch(
                "narrare.writing.deps_story_suggest.get_invocation_pipeline",
                return_value=MagicMock(spec=["prepare", "finalize"]),
            ),
            patch(
                "narrare.writing.deps_story_suggest.NovelRepository",
                return_value=novel_repo,
            ),
        ):
            service = await get_story_suggest_service(
                session=MagicMock(spec=AsyncSession, name="session"),
                user_id=str(uuid4()),
                novel_id=uuid4(),
            )

        assert fake_resolver.resolve.await_count == 0, (
            "routing cascade must not run at construction"
        )
        assert novel_repo.get_by_id.await_count == 0, (
            "uid-scoped novel guard must not run at construction (moved to "
            "the service's first use — planning guard ruling)"
        )
        assert service is not None

    async def test_factory_wires_lazy_resolution_with_eager_args(self) -> None:
        """The wired seam resolves with the eager factory's verbatim
        SUGGEST cascade args (intent, uid, novel_id) on first use."""
        from narrare.writing.deps_story_suggest import get_story_suggest_service
        from narrare_core.llm.intents import LLMIntent

        uid = uuid4()
        novel_id = uuid4()
        fake_resolver = MagicMock(spec=["resolve"])
        fake_resolver.resolve = AsyncMock(return_value=_resolved_model())
        novel_repo = MagicMock(spec=["get_by_id"], get_by_id=AsyncMock(return_value=make_novel()))

        with (
            patch(
                "narrare.writing.deps_story_suggest.get_model_routing_resolver",
                return_value=fake_resolver,
            ),
            patch(
                "narrare.writing.deps_story_suggest.get_model_registry",
                return_value=MagicMock(spec=["prepare"]),
            ),
            patch(
                "narrare.writing.deps_story_suggest.get_composer",
                return_value=MagicMock(spec=["build"]),
            ),
            patch(
                "narrare.writing.deps_story_suggest.get_invocation_pipeline",
                return_value=MagicMock(spec=["prepare", "finalize"]),
            ),
            patch(
                "narrare.writing.deps_story_suggest.NovelRepository",
                return_value=novel_repo,
            ),
        ):
            service = await get_story_suggest_service(
                session=MagicMock(spec=AsyncSession, name="session"),
                user_id=str(uid),
                novel_id=novel_id,
            )
            assert service._config is None, "no config may be cached at wiring"
            await service._model_resolution.resolve()

        fake_resolver.resolve.assert_awaited_once_with(LLMIntent.SUGGEST, uid, novel_id)


# ---------------------------------------------------------------------------
# Service-level: first-use resolve + graceful degradation
# ---------------------------------------------------------------------------


class TestGracefulFirstUse:
    """First use resolves once; ``ConfigurationError`` degrades, not raises."""

    async def test_validate_suggest_resolves_once_and_is_idempotent(self) -> None:
        """The pre-stream seam runs the cascade ONCE and caches the config;
        repeat calls return without re-running the cascade (ADR-086
        contract #2)."""
        resolution = _CountingResolution(_resolved_model())
        service = _make_service(resolution, make_novel())
        novel_id = uuid4()
        user_id = uuid4()

        await service.validate_suggest(novel_id, user_id)
        await service.validate_suggest(novel_id, user_id)

        assert resolution.calls == 1
        assert service._config is _CASCADE_CONFIG

    async def test_entry_point_resolves_exactly_once(self) -> None:
        """Seam + full ``suggest`` stream together trigger exactly ONE
        cascade run (the seam's resolve is the cached one)."""
        resolution = _CountingResolution(_resolved_model())
        service = _make_service(resolution, make_novel())

        await service.validate_suggest(uuid4(), uuid4())
        await _run_suggest(service)

        assert resolution.calls == 1

    async def test_novel_guard_precedes_resolution(self) -> None:
        """Missing novel → NotFoundError and the cascade NEVER runs.

        The relocated uid-scoped guard stays ahead of the resolve —
        eager-world precedence (planning guard ruling).
        """
        resolution = _CountingResolution(_resolved_model())
        service = _make_service(resolution, novel=None)

        with pytest.raises(NotFoundError, match="Novel"):
            await service.validate_suggest(uuid4(), uuid4())

        assert resolution.calls == 0, "resolution must not run before the novel guard"

    async def test_suggest_guard_precedes_resolution(self) -> None:
        """The ``suggest`` entry point keeps the same gate-before-
        resolution ordering for direct callers (no seam involved)."""
        resolution = _CountingResolution(_resolved_model())
        service = _make_service(resolution, novel=None)

        with pytest.raises(NotFoundError, match="Novel"):
            await _run_suggest(service)

        assert resolution.calls == 0, "resolution must not run before the novel guard"

    async def test_no_provider_degrades_to_no_model_config_outcome(self) -> None:
        """No AI provider → the preserved degraded outcome, NOT a raised
        ``ConfigurationError`` (RULE-11 sanctioned graceful exception).

        The first-use path logs the eager factory's
        ``no_ai_provider_configured`` event and the existing
        ``no_model_config`` NotFoundError fires in-band — the eager
        factory's swallow semantics moved, WHAT unchanged.
        """
        resolution = _CountingResolution(model=None)
        service = _make_service(resolution, make_novel())

        # The pre-stream seam swallows (AI-optional feature): no raise.
        with patch("narrare.writing.story_suggest_service.logger") as fake_logger:
            await service.validate_suggest(uuid4(), uuid4())

        assert resolution.calls == 1
        fake_logger.info.assert_called_once()
        event = fake_logger.info.call_args.args[0]
        assert event == "no_ai_provider_configured", (
            "degradation must log the eager factory's event verbatim"
        )

        # The degraded outcome fires in the entry point, in-band, exactly
        # as it did when the eager factory swallowed at wiring time.
        with pytest.raises(NotFoundError, match="no_model_config"):
            await _run_suggest(service)

    async def test_degraded_resolve_not_retried_on_second_call(self) -> None:
        """A failed resolve is cached as attempted — the cascade runs at
        most once per instance even across repeated entry-point calls
        (eager-world timing resolved exactly once per request too)."""
        resolution = _CountingResolution(model=None)
        service = _make_service(resolution, make_novel())

        for _ in range(2):
            with pytest.raises(NotFoundError, match="no_model_config"):
                await _run_suggest(service)

        assert resolution.calls == 1, "degraded resolve must not be retried"

    async def test_resolved_config_reaches_prepare(self) -> None:
        """The resolved config flows into ``registry.prepare`` verbatim —
        the eager factory's WHAT, timing-only moved (no credential
        overrides exist on this service; they default to None)."""
        resolution = _CountingResolution(_resolved_model())
        registry = FakeModelRegistry()
        novel_repo = MagicMock(spec=["get_by_id"], get_by_id=AsyncMock(return_value=make_novel()))
        from narrare.writing.story_suggest_service import StorySuggestService

        service = StorySuggestService(
            novel_repo=cast("NovelRepository", novel_repo),
            model_registry=cast("ModelRegistry", registry),
            model_resolution=resolution,
            composer=cast("PromptComposer", FakeComposer()),
        )

        await service.validate_suggest(uuid4(), uuid4())
        await _run_suggest(service)

        assert registry.prepare_calls, "prepare must run on the happy path"
        assert registry.prepare_calls[0]["config"] is _CASCADE_CONFIG
