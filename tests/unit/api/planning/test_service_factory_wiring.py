"""Wiring pins for the planning service factory — LAZY model routing
(ADR-086 L21).

Pins that ``get_storyboard_service`` constructs the governed
``AIRemapService`` (composer-based, provider-independent) and wires the
per-user PLAN cascade as a ``LazyModelResolution`` — resolving NOTHING
and querying NOVELS at construction time (the eager factory resolved
and ran its uid-scoped novel guard at wiring time; both moved to the
service's first use — ADR-086 regression contract #1 and the planning
guard ruling).

Construction-time neutrality is pinned against BOTH eager-world failure
modes: an erroring resolver and a missing novel must not prevent
construction — the graceful swallow and the 404 guard are first-use
policy now (see ``test_storyboard_lazy_resolution.py``).
"""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

from narrare.planning._service_factory import get_storyboard_service
from narrare.planning.service import StoryboardService
from narrare_core.llm.model_config import ResolvedModelConfig
from narrare_core.planning.remap import AIRemapService
from narrare_core.shared.errors import ConfigurationError
from tests.unit.api.planning._storyboard_test_helpers import (
    _CASCADE_CONFIG,
    make_resolved_model,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


class _FakeSession:
    """Inert session stand-in — the real repository is patched out."""


class _FakeNovelRepository:
    """Fake NovelRepository returning a seeded novel (or None); counts."""

    def __init__(self, novel: object | None = None) -> None:
        self._novel = novel
        self.get_by_id_calls = 0

    async def get_by_id(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> object | None:
        self.get_by_id_calls += 1
        return self._novel


class _FakeResolver:
    """Fake model routing resolver — records args; canned result/error."""

    def __init__(self, resolved: object | None = None, error: Exception | None = None) -> None:
        self._resolved = resolved
        self._error = error
        self.calls: list[tuple[object, object, object]] = []

    async def resolve(self, intent: object, user_id: object, novel_id: object) -> object:
        self.calls.append((intent, user_id, novel_id))
        if self._error is not None:
            raise self._error
        return self._resolved


def _patch_env(
    stack: ExitStack,
    novel: object,
    *,
    resolver: _FakeResolver,
    registry: object,
    composer: object,
    pipeline: object,
) -> _FakeNovelRepository:
    """Enter all factory dependency patches onto the stack."""

    def novel_repo_factory(_session: object) -> _FakeNovelRepository:
        return _FakeNovelRepository(novel=novel)

    stack.enter_context(
        patch("narrare.planning._service_factory.NovelRepository", novel_repo_factory)
    )
    stack.enter_context(
        patch(
            "narrare.planning._service_factory.get_model_routing_resolver",
            lambda _session: resolver,
        )
    )
    stack.enter_context(
        patch("narrare.planning._service_factory.get_model_registry", lambda: registry)
    )
    stack.enter_context(patch("narrare.planning._service_factory.get_composer", lambda: composer))
    stack.enter_context(
        patch(
            "narrare.planning._service_factory.get_invocation_pipeline",
            lambda: pipeline,
        )
    )
    return novel_repo_factory(None)


class TestStoryboardServiceFactoryWiring:
    """get_storyboard_service: lazy wiring — nothing runs at construction."""

    async def test_no_resolution_at_construction(self) -> None:
        """Factory entry runs ZERO cascades and issues ZERO novel queries.

        The eager factory ran the uid-scoped novel guard + the PLAN
        cascade at wiring time; both move to the service's first use
        (guard preserved per the planning guard ruling — asserted at
        service level in ``test_storyboard_lazy_resolution.py``).
        """
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        resolver = _FakeResolver(
            resolved=SimpleNamespace(
                config=_user_config(), api_key=_USER_KEY, base_url=_USER_BASE_URL
            )
        )
        with ExitStack() as stack:
            novel_repo = _patch_env(
                stack,
                MagicMock(spec=["id"]),
                resolver=resolver,
                registry=object(),
                composer=cast("object", object()),
                pipeline=object(),
            )
            service = await get_storyboard_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        assert len(resolver.calls) == 0, "routing cascade must not run at construction"
        assert novel_repo.get_by_id_calls == 0, (
            "uid-scoped novel guard must not run at construction (moved to "
            "the service's first use — planning guard ruling)"
        )
        assert isinstance(service, StoryboardService)

    async def test_factory_injects_ai_remap_service_with_composer(self) -> None:
        """THE activation pin: the governed remap service reaches the service."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        registry, composer, pipeline = object(), object(), object()
        with ExitStack() as stack:
            _patch_env(
                stack,
                MagicMock(spec=["id"]),
                resolver=_FakeResolver(resolved=make_resolved_model()),
                registry=registry,
                composer=composer,
                pipeline=pipeline,
            )
            service = await get_storyboard_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        assert isinstance(service._ai_remap_service, AIRemapService)
        assert service._invocation_pipeline is pipeline

    async def test_factory_wires_lazy_resolution_with_eager_args(self) -> None:
        """The wired lazy resolution resolves the SAME PLAN cascade with
        the SAME args the eager factory used verbatim (intent, uid,
        novel_id — timing-only, RULE-18) and caches the canned triple."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        uid = uuid.UUID(str(user_id))
        resolved = make_resolved_model(api_key=_USER_KEY, base_url=_USER_BASE_URL)
        resolver = _FakeResolver(resolved=resolved)
        with ExitStack() as stack:
            _patch_env(
                stack,
                MagicMock(spec=["id"]),
                resolver=resolver,
                registry=object(),
                composer=cast("object", object()),
                pipeline=object(),
            )
            service = await get_storyboard_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        from narrare_core.llm.intents import LLMIntent

        await service._resolution.ensure_resolved()

        assert len(resolver.calls) == 1
        intent, called_uid, called_novel_id = resolver.calls[0]
        assert intent is LLMIntent.PLAN
        assert called_uid == uid
        assert called_novel_id == novel_id
        assert service._resolution.config is _CASCADE_CONFIG
        assert service._resolution.api_key == _USER_KEY
        assert service._resolution.base_url == _USER_BASE_URL

    async def test_factory_constructs_when_resolver_would_fail(self) -> None:
        """An erroring resolver does not prevent construction — the eager
        factory's wiring-time graceful swallow is first-use policy now,
        so construction is neutral (0 cascade attempts)."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        resolver = _FakeResolver(error=ConfigurationError("no provider"))
        with ExitStack() as stack:
            _patch_env(
                stack,
                MagicMock(spec=["id"]),
                resolver=resolver,
                registry=object(),
                composer=cast("object", object()),
                pipeline=object(),
            )
            service = await get_storyboard_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        assert len(resolver.calls) == 0
        assert isinstance(service, StoryboardService)

    async def test_factory_constructs_without_novel_query_for_missing_novel(self) -> None:
        """A missing novel does not prevent construction — the eager
        factory's wiring-time 404 guard is first-use policy now, so
        construction issues no novel query at all."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        with ExitStack() as stack:
            novel_repo = _patch_env(
                stack,
                None,
                resolver=_FakeResolver(resolved=make_resolved_model()),
                registry=object(),
                composer=cast("object", object()),
                pipeline=object(),
            )
            service = await get_storyboard_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        assert novel_repo.get_by_id_calls == 0
        assert isinstance(service, StoryboardService)
