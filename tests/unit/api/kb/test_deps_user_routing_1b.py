"""User-routing migration tests for kb dependency factories (Task 1b).

Regression-first proof that the kb session/worldbuilding/consistency
factories wire the per-user ``ModelRoutingResolver`` cascade (instead of
the legacy ``build_system_default_config``) with the correct intent +
user_id + novel_id, and that the resolved config lands on the services
that own the actual ``get_model``/``run`` calls. The session factory
wires the cascade LAZILY — resolved at the assist service's first use,
never at construction (ADR-086 L18); the worldbuilding/consistency
entries are still eager until their ledger slices land.

Credential flow into those resolution points is proven in the companion
``test_deps_user_routing_1b_credentials.py`` (split off for the RULE-04
test-file hard limit). Sibling of ``test_deps_user_routing.py``
(Task 1a). Same conventions: fake resolver, cast-pattern registry fakes.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_deps_user_routing.py, Task 1a conventions)
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
    """A spec'd fake resolver whose resolve() returns the user's model."""
    resolved = _resolved()
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(return_value=resolved)
    return resolver, resolved


# ===========================================================================
# Structural — factories are async, user-scoped, legacy-pattern-free
# ===========================================================================

# (module, factory) pairs — parametrized to stay under the RULE-04 test-file
# hard limit while asserting each factory as its own test case.
_USER_ROUTED_FACTORIES = [
    ("narrare.kb.dependencies_session", "get_kb_session_service"),
    ("narrare.kb.dependencies_worldbuilding", "get_worldbuilding_service"),
    ("narrare.kb._consistency_deps", "get_consistency_service"),
]


class TestFactoryStructure:
    """Structural regressions: signature gains user routing, legacy is gone."""

    @pytest.mark.parametrize(("module_name", "factory_name"), _USER_ROUTED_FACTORIES)
    def test_factory_is_async_with_user_routing_params(
        self, module_name: str, factory_name: str
    ) -> None:
        import importlib

        factory = getattr(importlib.import_module(module_name), factory_name)

        assert inspect.iscoroutinefunction(factory)
        params = list(inspect.signature(factory).parameters)
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    @pytest.mark.parametrize("module_name", [m for m, _ in _USER_ROUTED_FACTORIES])
    def test_factory_does_not_use_system_default_config(self, module_name: str) -> None:
        import importlib

        source = inspect.getsource(importlib.import_module(module_name))
        assert "build_system_default_config" not in source
        assert "SystemModelCategory" not in source


# ===========================================================================
# Factory execution — resolver resolves with intent + user_id + novel_id
# ===========================================================================


class TestSessionFactoryUserRouting:
    """get_kb_session_service wires the KB_INTERVIEW cascade lazily."""

    async def test_wires_kb_interview_cascade_lazily_for_user_and_novel(self) -> None:
        from narrare.kb.assist_service import KBAssistService
        from narrare.kb.dependencies_session import get_kb_session_service
        from narrare.kb.session_service import KBSessionService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.kb.dependencies_session.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare._app.dependencies.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare._app.dependencies.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare._app.dependencies.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ),
            patch(
                "narrare.kb.dependencies_core.get_kb_service",
                return_value=MagicMock(spec=True, name="KBService"),
            ),
        ):
            service = await get_kb_session_service(
                novel_id=novel_id,
                session=session,
                event_publisher=MagicMock(spec=True, name="WikiEventPublisher"),
                user_id=user_id,
            )

        # ADR-086 lazy wiring: construction resolves nothing.
        assert resolver.resolve.await_args_list == []

        assert isinstance(service, KBSessionService)
        assert isinstance(service._assist, KBAssistService)
        resolved_model = await service._assist.ensure_resolved()

        # The REAL intent (KB_INTERVIEW), for THIS user, WITH the novel
        # tier — invoked at first use, not at construction:
        assert resolver.resolve.await_args_list == [
            call(LLMIntent.KB_INTERVIEW, UUID(user_id), novel_id)
        ]

        # The cascade result lands on the assist service (threaded onwards
        # to ModelRegistry.prepare with the credentials).
        assert resolved_model.config is resolved.config
        assert resolved_model.api_key == _USER_KEY
        assert resolved_model.base_url == _USER_BASE_URL


class TestWorldbuildingFactoryUserRouting:
    """get_worldbuilding_service resolves via the cascade (KB_WORLDBUILD)."""

    async def test_resolves_kb_worldbuild_for_user_and_novel(self) -> None:
        from narrare.kb.dependencies_worldbuilding import get_worldbuilding_service
        from narrare.kb.worldbuilding_service import WorldbuildingService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.kb.dependencies_worldbuilding.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare._app.dependencies.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare._app.dependencies.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare._app.dependencies.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ),
        ):
            service = await get_worldbuilding_service(
                novel_id=novel_id,
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.KB_WORLDBUILD, UUID(user_id), novel_id)
        assert isinstance(service, WorldbuildingService)
        assert service._analyzer._config is resolved.config
        assert service._analyzer._api_key == _USER_KEY
        assert service._analyzer._base_url == _USER_BASE_URL


class TestConsistencyDepsUserRouting:
    """get_consistency_service resolves TWO configs: consistency + worldbuild."""

    async def test_resolves_kb_consistency_and_kb_worldbuild_for_user_and_novel(self) -> None:
        from narrare.kb._consistency_deps import get_consistency_service
        from narrare.kb.consistency_service import KBConsistencyService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
        resolved_consistency = _resolved()
        resolved_worldbuild = _resolved()
        resolver.resolve = AsyncMock(side_effect=[resolved_consistency, resolved_worldbuild])

        with (
            patch(
                "narrare.kb._consistency_deps.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare._app.dependencies.get_model_registry",
                return_value=MagicMock(spec=True, name="ModelRegistry"),
            ),
            patch(
                "narrare._app.dependencies.get_composer",
                return_value=MagicMock(spec=True, name="PromptComposer"),
            ),
            patch(
                "narrare._app.dependencies.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ),
            patch(
                "narrare.kb.dependencies.get_rel_service",
                return_value=MagicMock(spec=True, name="RelationshipService"),
            ),
            patch(
                "narrare.kb._feedback_memory_deps.get_consistency_feedback_memory_instance",
                return_value=MagicMock(spec=True, name="FeedbackMemory"),
            ),
        ):
            service = await get_consistency_service(
                novel_id=novel_id,
                session=session,
                user_id=user_id,
            )

        assert resolver.resolve.await_count == 2
        assert resolver.resolve.await_args_list == [
            call(LLMIntent.KB_CONSISTENCY, UUID(user_id), novel_id),
            call(LLMIntent.KB_WORLDBUILD, UUID(user_id), novel_id),
        ]
        assert isinstance(service, KBConsistencyService)
        assert service._analyzer._config is resolved_consistency.config
        assert service._analyzer._api_key == _USER_KEY
        assert service._worldbuilding_analyzer._config is resolved_worldbuild.config
        assert service._worldbuilding_analyzer._api_key == _USER_KEY
