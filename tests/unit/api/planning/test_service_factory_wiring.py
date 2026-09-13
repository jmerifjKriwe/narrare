"""Wiring pins for the planning service factory — AI remap activation (FO-9).

Pins that ``get_storyboard_service`` constructs and injects the governed
``AIRemapService`` (composer-based, provider-independent), threads the
resolved model routing + credentials, and degrades gracefully when no AI
provider is configured (RULE-11).
"""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest

from narrare.planning._service_factory import get_storyboard_service
from narrare.planning.service import StoryboardService
from narrare_core.llm import ResolvedModelConfig
from narrare_core.planning.remap import AIRemapService
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

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
    """Fake NovelRepository returning a seeded novel (or None)."""

    def __init__(self, novel: object | None = None) -> None:
        self._novel = novel

    async def get_by_id(self, novel_id: uuid.UUID, user_id: uuid.UUID) -> object | None:
        return self._novel


class _FakeResolver:
    """Fake model routing resolver — returns a canned resolution or raises."""

    def __init__(self, resolved: object | None = None, error: Exception | None = None) -> None:
        self._resolved = resolved
        self._error = error

    async def resolve(self, intent: object, user_id: object, novel_id: object) -> object:
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
) -> None:
    """Enter all factory dependency patches onto the stack."""

    def novel_repo_factory(_session: object) -> object:
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


class TestStoryboardServiceFactoryWiring:
    """get_storyboard_service: AIRemapService injection + routing pass-through."""

    async def test_factory_injects_ai_remap_service_with_composer(self) -> None:
        """THE activation pin: the governed remap service reaches the service."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        registry, composer, pipeline = object(), object(), object()
        resolved = SimpleNamespace(config=_user_config(), api_key=None, base_url=None)
        with ExitStack() as stack:
            _patch_env(
                stack,
                MagicMock(spec=["id"]),
                resolver=_FakeResolver(resolved=resolved),
                registry=registry,
                composer=composer,
                pipeline=pipeline,
            )
            service = await get_storyboard_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        assert isinstance(service, StoryboardService)
        assert isinstance(service._ai_remap_service, AIRemapService)
        assert service._invocation_pipeline is pipeline

    async def test_factory_threads_model_routing_and_credentials(self) -> None:
        """Resolved config, registry, api_key, and base_url reach the service."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        config = _user_config()
        registry = cast("ModelRegistry", object())
        resolved = SimpleNamespace(config=config, api_key=_USER_KEY, base_url=_USER_BASE_URL)
        with ExitStack() as stack:
            _patch_env(
                stack,
                MagicMock(spec=["id"]),
                resolver=_FakeResolver(resolved=resolved),
                registry=registry,
                composer=cast("PromptComposer", object()),
                pipeline=object(),
            )
            service = await get_storyboard_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        assert service._model_config is config
        assert service._model_registry is registry
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL

    async def test_factory_degrades_gracefully_without_provider(self) -> None:
        """No provider: model config is None, remap service stays injected."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        with ExitStack() as stack:
            _patch_env(
                stack,
                MagicMock(spec=["id"]),
                resolver=_FakeResolver(error=ConfigurationError("no provider")),
                registry=object(),
                composer=cast("PromptComposer", object()),
                pipeline=object(),
            )
            service = await get_storyboard_service(
                cast("AsyncSession", _FakeSession()), str(user_id), novel_id
            )

        assert service._model_config is None
        assert service._api_key is None
        assert service._base_url is None
        assert isinstance(service._ai_remap_service, AIRemapService)

    async def test_factory_raises_for_missing_novel(self) -> None:
        """Nonexistent novel raises NotFoundError (before resolver runs)."""
        novel_id, user_id = uuid.uuid4(), uuid.uuid4()
        with ExitStack() as stack:
            _patch_env(
                stack,
                None,
                resolver=_FakeResolver(),
                registry=object(),
                composer=cast("PromptComposer", object()),
                pipeline=object(),
            )
            with pytest.raises(NotFoundError):
                await get_storyboard_service(
                    cast("AsyncSession", _FakeSession()), str(user_id), novel_id
                )
