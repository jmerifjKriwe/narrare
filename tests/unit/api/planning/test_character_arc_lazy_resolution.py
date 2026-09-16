"""Lazy factory wiring + graceful first-use resolve of CharacterArcService
(ADR-086 L20, Pattern M-graceful).

Factory-level + service-level halves of the L20 lazy contract:

- ``get_character_arc_service`` runs ZERO cascades and issues ZERO novel
  queries at construction time — the eager factory's uid-scoped novel
  guard ran at wiring time; per the ADR-086 planning guard ruling it is
  preserved (not dropped) as the SERVICE entry point's existing uid-scoped
  guard, which runs immediately BEFORE the first-use resolve
  (gate-before-resolution ordering).
- First use (``ensure_resolved``) runs the per-user PLAN routing cascade
  EXACTLY ONCE, cached and idempotent (eager-world timing also resolved
  exactly once per request).
- Graceful degradation is service policy (RULE-11 sanctioned exception):
  ``ConfigurationError`` (no AI provider) is caught at the entry point,
  logged (``no_ai_provider_configured`` — the eager factory's event,
  byte-identical), and leaves the triple unset so the preserved
  ``no_model_config`` degraded outcome fires — the eager factory's
  swallow semantics moved past validation, WHAT unchanged.

Mirrors ``tests/unit/api/writing/test_deps_style_variants_lazy_wiring.py``
(ADR-086 L35 convention) and the series L26 service-level shape.

See:
    ADR-086 — lazy model resolution (L20; Pattern M-graceful)
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
from tests.unit.api.planning._character_arc_test_helpers import (
    FakeComposer,
    FakeModelRegistry,
    make_agent_output,
    make_novel,
    make_request,
)

if TYPE_CHECKING:
    from narrare.novels.repository import NovelRepository
    from narrare.planning.character_arc_service import CharacterArcService
    from narrare.planning.schemas import CharacterArcRequest
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


def _resolved_model(**kw: str | None) -> ResolvedModel:
    """A fixed model triple, as the routing cascade would return it."""
    return ResolvedModel(
        config=_CASCADE_CONFIG,
        api_key=kw.get("api_key"),
        base_url=kw.get("base_url"),
        source="unit-test",
    )


def _make_service(
    resolution: _CountingResolution,
    novel: object | None,
) -> CharacterArcService:
    """Build a CharacterArcService wired with a counting resolution."""
    from narrare.planning.character_arc_service import CharacterArcService

    novel_repo = MagicMock(spec=["get_by_id"], get_by_id=AsyncMock(return_value=novel))
    return CharacterArcService(
        novel_repo=cast("NovelRepository", novel_repo),
        model_registry=cast("ModelRegistry", FakeModelRegistry()),
        model_resolution=resolution,
        composer=cast("PromptComposer", FakeComposer()),
    )


async def _run_entry(service: CharacterArcService, request: CharacterArcRequest) -> object:
    """Run ``generate_character_arc`` with the agent boundary patched out."""
    with (
        patch("narrare_core.agents.character_arc_agent.CharacterArcAgent") as mock_agent_cls,
        patch("narrare_core.agents.character_arc_agent.CharacterArcDeps"),
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
        return await service.generate_character_arc(uuid4(), uuid4(), request)


# ---------------------------------------------------------------------------
# Factory-level: nothing at construction (ADR-086 regression contract #1)
# ---------------------------------------------------------------------------


class TestLazyFactoryWiring:
    """``get_character_arc_service`` resolves NOTHING at construction."""

    async def test_no_resolution_at_construction(self) -> None:
        """Factory entry runs ZERO cascades and issues ZERO novel queries.

        The eager factory ran the uid-scoped novel guard + the PLAN
        cascade at wiring time; both move to the service's first use
        (guard preserved per the planning guard ruling — asserted at
        service level in ``TestGracefulFirstUse``).
        """
        from narrare.planning._character_arc_factory import get_character_arc_service

        fake_resolver = MagicMock(spec=["resolve"])
        fake_resolver.resolve = AsyncMock(return_value=_resolved_model())
        novel_repo = MagicMock(spec=["get_by_id"], get_by_id=AsyncMock(return_value=make_novel()))

        with (
            patch(
                "narrare.planning._character_arc_factory.get_model_routing_resolver",
                return_value=fake_resolver,
            ),
            patch(
                "narrare.planning._character_arc_factory.get_model_registry",
                return_value=MagicMock(spec=["prepare"]),
            ),
            patch(
                "narrare.planning._character_arc_factory.get_composer",
                return_value=MagicMock(spec=["build"]),
            ),
            patch(
                "narrare.planning._character_arc_factory.get_invocation_pipeline",
                return_value=MagicMock(spec=["prepare", "finalize"]),
            ),
            patch(
                "narrare.planning._character_arc_factory.NovelRepository",
                return_value=novel_repo,
            ),
        ):
            service = await get_character_arc_service(
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


# ---------------------------------------------------------------------------
# Service-level: first-use resolve + graceful degradation
# ---------------------------------------------------------------------------


class TestGracefulFirstUse:
    """First use resolves once; ``ConfigurationError`` degrades, not raises."""

    async def test_ensure_resolved_resolves_once_and_is_idempotent(self) -> None:
        """First use runs the cascade ONCE and caches the triple; repeat
        calls return without re-running the cascade (ADR-086 contract #2)."""
        resolution = _CountingResolution(_resolved_model(api_key="sk-user"))
        service = _make_service(resolution, make_novel())

        await service.ensure_resolved()
        await service.ensure_resolved()

        assert resolution.calls == 1
        assert service._config is _CASCADE_CONFIG
        assert service._api_key == "sk-user"
        assert service._base_url is None

    async def test_entry_point_resolves_exactly_once(self) -> None:
        """The full entry point triggers exactly ONE cascade run."""
        resolution = _CountingResolution(_resolved_model())
        service = _make_service(resolution, make_novel())

        await _run_entry(service, make_request())

        assert resolution.calls == 1

    async def test_novel_guard_precedes_resolution(self) -> None:
        """Missing novel → NotFoundError and the cascade NEVER runs.

        The uid-scoped guard (service-side since L20) stays ahead of the
        resolve — eager-world precedence (planning guard ruling).
        """
        resolution = _CountingResolution(_resolved_model())
        service = _make_service(resolution, novel=None)

        with pytest.raises(NotFoundError, match="Novel"):
            await _run_entry(service, make_request())

        assert resolution.calls == 0, "resolution must not run before the novel guard"

    async def test_no_provider_degrades_to_no_model_config_outcome(self) -> None:
        """No AI provider → the preserved degraded outcome, NOT a raised
        ``ConfigurationError`` (RULE-11 sanctioned graceful exception).

        The entry point logs the eager factory's ``no_ai_provider_configured``
        event and the existing ``no_model_config`` NotFoundError fires —
        the eager factory's swallow semantics moved past validation.
        """
        resolution = _CountingResolution(model=None)
        service = _make_service(resolution, make_novel())

        with (
            patch("narrare.planning.character_arc_service.logger") as fake_logger,
            pytest.raises(NotFoundError, match="no_model_config"),
        ):
            await _run_entry(service, make_request())

        assert resolution.calls == 1
        fake_logger.info.assert_called_once()
        event = fake_logger.info.call_args.args[0]
        assert event == "no_ai_provider_configured", (
            "degradation must log the eager factory's event verbatim"
        )

    async def test_degraded_resolve_not_retried_on_second_call(self) -> None:
        """A failed resolve is cached as attempted — the cascade runs at
        most once per instance even across repeated entry-point calls
        (eager-world timing resolved exactly once per request too)."""
        resolution = _CountingResolution(model=None)
        service = _make_service(resolution, make_novel())

        for _ in range(2):
            with pytest.raises(NotFoundError, match="no_model_config"):
                await _run_entry(service, make_request())

        assert resolution.calls == 1, "degraded resolve must not be retried"

    async def test_resolved_triple_reaches_prepare(self) -> None:
        """The resolved triple flows into ``registry.prepare`` verbatim —
        the eager factory's WHAT (config + credentials), timing-only moved."""
        resolution = _CountingResolution(_resolved_model(api_key="sk-user"))
        registry = FakeModelRegistry()
        novel_repo = MagicMock(spec=["get_by_id"], get_by_id=AsyncMock(return_value=make_novel()))
        from narrare.planning.character_arc_service import CharacterArcService

        service = CharacterArcService(
            novel_repo=cast("NovelRepository", novel_repo),
            model_registry=cast("ModelRegistry", registry),
            model_resolution=resolution,
            composer=cast("PromptComposer", FakeComposer()),
        )

        await _run_entry(service, make_request())

        registry.get_model.assert_awaited_once()
        kwargs = registry.get_model.call_args.kwargs
        assert kwargs.get("api_key") == "sk-user"
        assert kwargs.get("base_url") is None
