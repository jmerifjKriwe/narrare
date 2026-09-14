"""Lazy model-resolution semantics for NameGeneratorService (ADR-086 L14).

The factory (``generation/router.py::_get_service``) wires a
``LazyModelResolution``; this file pins the SERVICE-side lazy contract:

- no resolution at construction,
- exactly one resolve at first use, idempotent afterwards,
- ``ConfigurationError`` propagates un-swallowed from the entry point
  (RULE-11 — AI-mandatory endpoint),
- the generation sampling overrides (temperature/max_tokens) layer onto
  the resolved config at first use — moved verbatim from the eager
  factory (timing-only migration: WHAT unchanged, only WHEN).

Mirrors ``tests/unit/api/analysis/test_voice_drift_service_errors.py``
(ADR-086 L11 precedent).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest

from narrare.generation.name_service import NameGeneratorService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.llm.model_routing import ResolvedModel
from narrare_core.shared.errors import ConfigurationError
from tests.fakes.fake_llm_gateway import FakeModelRegistry

from ._ownership_fakes import permissive_novel_repo
from .conftest import _default_request, _json_names_response, _static_resolution

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from narrare._app.dependencies_services import ModelResolution
    from narrare_core.prompts.composer import PromptComposer


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
    registry: FakeModelRegistry,
    composer: AsyncMock | PromptComposer,
) -> NameGeneratorService:
    """Build a NameGeneratorService with the lazy seam injected."""
    return NameGeneratorService(
        registry=registry,
        composer=cast("PromptComposer", composer),
        model_resolution=model_resolution,
        novel_repo=permissive_novel_repo(),
    )


class TestLazyResolutionContract:
    """ADR-086 lazy resolution at the NameGeneratorService boundary."""

    async def test_no_resolution_at_construction(
        self,
        mock_composer: AsyncMock,
    ) -> None:
        """Construction must not touch the routing cascade."""
        counting = _CountingResolution(_resolved_model())

        _make_service(counting, FakeModelRegistry(), mock_composer)

        assert counting.calls == 0

    async def test_ensure_resolved_resolves_once_and_is_idempotent(
        self,
        mock_composer: AsyncMock,
    ) -> None:
        """First use resolves exactly once; repeat calls hit the cache."""
        counting = _CountingResolution(_resolved_model())
        service = _make_service(counting, FakeModelRegistry(), mock_composer)

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert counting.calls == 1
        assert first is second

    async def test_generate_names_resolves_exactly_once(
        self,
        mock_composer: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """The entry point is the first-use seam — one resolve per service."""
        registry = FakeModelRegistry()
        registry.returns(_json_names_response([{"name": "Zara", "meaning": "x"}]))
        counting = _CountingResolution(_resolved_model(config))
        service = _make_service(counting, registry, mock_composer)

        await service.generate_names(_default_request(), user_id=uuid.uuid4())

        assert counting.calls == 1

    async def test_resolver_configuration_error_propagates_un_swallowed(
        self,
        mock_composer: AsyncMock,
    ) -> None:
        """RULE-11 / ADR-086: the cascade's ``ConfigurationError``
        (unconfigured provider) propagates from the entry point — the
        service never swallows it (AI-mandatory endpoint). The ownership
        gate runs FIRST and passes (permissive repo), so the error comes
        from resolution, proving gates stay ahead of resolution."""

        service = _make_service(_RaisingResolution(), FakeModelRegistry(), mock_composer)

        with pytest.raises(ConfigurationError):
            await service.generate_names(_default_request(), user_id=uuid.uuid4())

    async def test_generation_overrides_layered_at_first_use(
        self,
        mock_composer: AsyncMock,
    ) -> None:
        """Timing-only invariant: the eager factory layered
        ``temperature=0.8, max_tokens=2000`` onto the resolved config —
        the lazy service layers the SAME values at first use, whatever
        the cascade returned."""
        resolved_config = ResolvedModelConfig(
            provider_name="test",
            model_id="test-model",
            temperature=0.1,
            max_tokens=100,
        )
        registry = FakeModelRegistry()
        registry.returns(_json_names_response([{"name": "Zara", "meaning": "x"}]))
        service = _make_service(_static_resolution(resolved_config), registry, mock_composer)

        await service.generate_names(_default_request(), user_id=uuid.uuid4())

        call = registry.last_call()
        assert call.config is not None
        assert call.config.temperature == 0.8
        assert call.config.max_tokens == 2000
