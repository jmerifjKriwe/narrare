"""User-routing migration tests for the chat dependency factory (Task 4).

Regression-first proof that ``chat/dependencies.get_chat_service`` wires
the chat model via the per-user ``ModelRoutingResolver`` cascade (instead
of the legacy ``build_system_default_config``) with the correct intent +
user_id, and that the resolved config + credentials land on the service
that owns the actual ``get_model`` call:

- Chat model — ``LLMIntent.CHAT`` (the intent ChatService composes its
  prompt with, ``chat_service.py`` ``self._composer.build(LLMIntent.CHAT,
  ...)``)

ADR-086 L12 (lazy migration): the factory no longer resolves — it wires
the cascade as a ``LazyModelResolution`` (zero resolve calls at
construction) and the SERVICE's first use (``ensure_resolved``) triggers
exactly one resolve with the verbatim eager args
(``(LLMIntent.CHAT, user_id, None)``); the returned triple is cached on
the service and threaded onwards to the ``get_model`` resolution point.

Auth posture (plan Task 4 verification): ALL chat router endpoints declare
``CurrentUserIdDep`` — JWT-mandatory (401 on missing/invalid token, see
``narrare._app.dependencies_auth.get_current_user_id``). There is NO
anonymous path, so the migration is FULL — no system-default branch for an
anonymous case. The router has no novel path parameter (``project_id``
arrives in the request body), so the cascade runs WITHOUT the project tier
per the migration plan ("where not, resolve without it").

Credential flow into the real resolution point (``ChatService`` ->
``ModelRegistry.get_model``) is proven in
``TestCredentialsReachResolutionPoint`` (setup-bug shape). Sibling of
``tests/unit/api/consistency/test_deps_user_routing.py`` (Task 3) — same
conventions: fake resolver, recording registry, cast-pattern fakes.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.chat.contracts import ChatRequest
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.chat.conversation_store import InMemoryConversationStore
    from narrare_core.llm.gateway import ModelRegistry

# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_deps_user_routing.py, Task 3 conventions)
# ---------------------------------------------------------------------------

_USER_KEY = "sk-user-key"
_USER_BASE_URL = "https://user.example/v1"


def _user_config() -> ResolvedModelConfig:
    """The config a wired-up user's resolver would return (wizard provider)."""
    return ResolvedModelConfig(
        provider_name="zai",
        model_id="glm-4.7",
        temperature=0.7,
        max_tokens=4096,
    )


def _resolved() -> ResolvedModel:
    """A ResolvedModel as the wired-up user's cascade would return."""
    return ResolvedModel(
        config=_user_config(),
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
    )


def _fake_resolver() -> tuple[MagicMock, ResolvedModel]:
    """A spec'd fake resolver returning one resolved model."""
    resolved = _resolved()
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(return_value=resolved)
    return resolver, resolved


def _mock_composer() -> AsyncMock:
    """Mock PromptComposer returning a known ComposedPrompt (conftest shape)."""
    from narrare_core.prompts.composer import ComposedPrompt

    composer = AsyncMock(name="PromptComposer")
    composer.build = AsyncMock(
        return_value=ComposedPrompt(system="System prompt.", user="User prompt.")
    )
    return composer


class _StopResolution(Exception):
    """Sentinel raised after get_model recorded its call (short-circuits)."""


class _RecordingRegistry:
    """Fake ModelRegistry — records ``get_model`` calls for asserts."""

    def __init__(self, stop_after_record: BaseException | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._stop = stop_after_record

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        self.calls.append({"config": config, "api_key": api_key, "base_url": base_url})
        if self._stop is not None:
            raise self._stop
        return object()

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: object = None,
        usage_limits: object = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> object:
        """Task-6d bridge: resolution flows through prepare → get_model.

        Delegates to the SAME recording ``get_model`` call so the
        credential assertions (``registry.calls`` shape) hold for the
        migrated (prepare) path under test.
        """
        return SimpleNamespace(
            model=await self.get_model(config, api_key=api_key, base_url=base_url),
            model_settings=None,
            usage_limits=usage_limits,
        )


# ===========================================================================
# Structural — factory is async, user-scoped, legacy-pattern-free
# ===========================================================================

_FACTORY = ("narrare.chat.dependencies", "get_chat_service")


class TestFactoryStructure:
    """Structural regressions: signature gains user routing, legacy is gone."""

    def test_factory_is_async_with_user_routing_params(self) -> None:
        import importlib

        factory = getattr(importlib.import_module(_FACTORY[0]), _FACTORY[1])

        assert inspect.iscoroutinefunction(factory)
        params = list(inspect.signature(factory).parameters)
        assert "user_id" in params
        assert "session" in params

    def test_factory_does_not_use_system_default_config(self) -> None:
        import importlib

        source = inspect.getsource(importlib.import_module(_FACTORY[0]))
        assert "build_system_default_config" not in source
        assert "SystemModelCategory" not in source


# ===========================================================================
# Factory execution — resolver resolves CHAT + threads results
# ===========================================================================


class TestChatDepsUserRouting:
    """get_chat_service lazily wires CHAT for THIS user (auth-mandatory router)."""

    async def test_no_resolution_at_construction(self) -> None:
        """ADR-086 L12: the factory wires the cascade — it never resolves."""
        from narrare.chat.chat_service import ChatService
        from narrare.chat.dependencies import get_chat_service

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, _resolved = _fake_resolver()

        with (
            patch(
                "narrare.chat.dependencies.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare.chat.dependencies.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare.chat.dependencies.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare.chat.dependencies.get_invocation_pipeline",
                return_value=None,
            ),
        ):
            service = await get_chat_service(
                session=session,
                user_id=user_id,
            )

        assert isinstance(service, ChatService)
        assert resolver.resolve.await_count == 0

    async def test_first_use_resolves_verbatim_args_and_caches_triple(self) -> None:
        """First use resolves once with the eager factory's verbatim args.

        The cascade runs ``(LLMIntent.CHAT, user_id, None)`` — the SAME
        intent (ChatService composes with CHAT), for THIS user, WITHOUT
        the project tier (project_id arrives in the request body — the
        router has no novel path parameter). The resolved triple is
        cached on the service and threaded onwards to the ``get_model``
        resolution point in ``_agent_stream``.
        """
        from narrare.chat.dependencies import get_chat_service

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.chat.dependencies.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare.chat.dependencies.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare.chat.dependencies.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare.chat.dependencies.get_invocation_pipeline",
                return_value=None,
            ),
        ):
            service = await get_chat_service(
                session=session,
                user_id=user_id,
            )

        first = await service.ensure_resolved()
        second = await service.ensure_resolved()

        assert resolver.resolve.await_args_list == [call(LLMIntent.CHAT, UUID(user_id), None)]
        assert first is second is resolved

        config = first.config
        assert isinstance(config, ResolvedModelConfig)
        assert config.model_id == "glm-4.7"
        assert config.provider_name == "zai"
        # Resolved user credentials ride the cached triple (threaded
        # onwards to the get_model resolution point in _agent_stream).
        assert first.api_key == _USER_KEY
        assert first.base_url == _USER_BASE_URL


# ===========================================================================
# Resolution point — credentials reach ModelRegistry.get_model
# ===========================================================================


class TestCredentialsReachResolutionPoint:
    """The resolved key must flow into the ACTUAL resolution call (setup bug)."""

    def _in_memory_store(self) -> InMemoryConversationStore:
        from narrare_core.chat.conversation_store import InMemoryConversationStore

        return InMemoryConversationStore()

    async def test_ask_threads_credentials_into_get_model(self) -> None:
        from narrare._app.dependencies_services import StaticModelResolution
        from narrare.chat.chat_service import ChatService

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service = ChatService(
            prompt_composer=_mock_composer(),
            model_registry=cast("ModelRegistry", registry),
            conversation_store=cast("SQLAlchemyConversationStore", self._in_memory_store()),
            model_resolution=StaticModelResolution(_resolved()),
        )
        request = ChatRequest(project_id=uuid4(), message="Hello!")

        stream = await service.ask(request, uuid4())
        with pytest.raises(_StopResolution):
            await self._drain(stream)

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]

    async def _drain(self, stream: AsyncIterator[dict[str, object]]) -> None:
        """Consume the SSE event stream (get_model fires on first anext)."""
        async for _event in stream:
            pass
