"""Wiring pins for the scene-AI factory — LAZY model routing (PLAN-001 T8).

Pins that ``get_scene_ai_service`` (mirroring ``get_storyboard_service``,
ADR-086 L21) wires the per-user PLAN cascade as a ``LazyModelResolution``
— resolving NOTHING at construction — and wires registry + composer
eagerly. The uid-scoped novel guard and the graceful no-provider
degradation are first-use service policy (asserted at service level in
``test_scene_ai_guards.py``).
"""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

from narrare._app.dependencies_services import LazyModelResolution
from narrare.planning._scene_ai_factory import get_scene_ai_service
from narrare.planning.scene_ai_service import SceneAIService
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class _FakeSession:
    """Inert session stand-in — the real repositories are patched out."""


class _FakeResolver:
    """Fake model routing resolver — records args; canned result."""

    def __init__(self, resolved: object) -> None:
        self._resolved = resolved
        self.calls: list[tuple[object, object, object]] = []

    async def resolve(self, intent: object, user_id: object, novel_id: object) -> object:
        self.calls.append((intent, user_id, novel_id))
        return self._resolved


class _FakeRepos:
    """Inert repository stand-ins (ownership guards are first-use policy)."""


def _patch_env(
    stack: ExitStack, *, resolver: _FakeResolver, registry: object, composer: object
) -> None:
    """Enter all factory dependency patches onto the stack."""

    def repo_factory(_session: object) -> _FakeRepos:
        return _FakeRepos()

    stack.enter_context(
        patch("narrare.planning._scene_ai_factory.ScenePlanRepository", repo_factory)
    )
    stack.enter_context(patch("narrare.planning._scene_ai_factory.ChapterRepository", repo_factory))
    stack.enter_context(patch("narrare.planning._scene_ai_factory.NovelRepository", repo_factory))
    stack.enter_context(
        patch(
            "narrare.planning._scene_ai_factory.get_model_routing_resolver",
            lambda _session: resolver,
        )
    )
    stack.enter_context(
        patch("narrare.planning._scene_ai_factory.get_model_registry", lambda: registry)
    )
    stack.enter_context(patch("narrare.planning._scene_ai_factory.get_composer", lambda: composer))


class TestSceneAIServiceFactoryWiring:
    """get_scene_ai_service: lazy PLAN cascade, eager registry/composer."""

    async def test_no_resolution_at_construction(self) -> None:
        """Factory entry runs ZERO cascades; service type is SceneAIService."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        resolver = _FakeResolver(resolved=MagicMock(spec=["config", "api_key", "base_url"]))
        registry, composer = object(), object()
        with ExitStack() as stack:
            _patch_env(stack, resolver=resolver, registry=registry, composer=composer)
            service = await get_scene_ai_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        assert len(resolver.calls) == 0, "routing cascade must not run at construction"
        assert isinstance(service, SceneAIService)

    async def test_lazy_resolution_defers_to_first_use(self) -> None:
        """The wired resolution is Lazy; resolve() hits (PLAN, uid, novel_id)."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        uid = uuid.UUID(str(user_id))
        resolved = MagicMock(spec=["config", "api_key", "base_url"])
        resolver = _FakeResolver(resolved=resolved)
        with ExitStack() as stack:
            _patch_env(
                stack,
                resolver=resolver,
                registry=object(),
                composer=object(),
            )
            service = await get_scene_ai_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        model_resolution = service._model_resolution
        assert isinstance(model_resolution, LazyModelResolution)
        assert await model_resolution.resolve() is resolved
        assert resolver.calls == [(LLMIntent.PLAN, uid, novel_id)]

    async def test_registry_and_composer_wire_eagerly(self) -> None:
        """Registry + composer instances reach the service at wiring time."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        registry, composer = object(), object()
        with ExitStack() as stack:
            _patch_env(
                stack,
                resolver=_FakeResolver(resolved=MagicMock(spec=["config"])),
                registry=registry,
                composer=composer,
            )
            service = await get_scene_ai_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        assert service._registry is registry
        assert service._composer is composer
