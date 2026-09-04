"""Unit tests for wiki/dependencies.py — DI factory functions.

Tests the session-to-repository wiring, the system-mode factory
closure, and the async factory functions that wire core wiki deps.

Task 6 user-routing migration: ``get_wiki_service`` resolves via the
per-user ``ModelRoutingResolver`` cascade (real intent SUMMARIZE, with
the novel_id project tier — all wiki routes are novel-scoped), and
``build_core_wiki_service`` serves two planes: user plane (resolved
config + credentials) and operator plane (system default, reserved for
the startup wiki listener in ``_app/lifespan.py``).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare.wiki.dependencies import (
    get_wiki_repository,
    get_wiki_service,
    make_system_wiki_factory,
)
from narrare.wiki.dependencies_core import build_core_wiki_service
from narrare.wiki.repository import WikiRepository
from narrare.wiki.service import APIWikiService
from narrare_core.llm import ModelRegistry, ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel
from tests.fakes.fake_core_wiki_service import FakeCoreWikiService

# ---------------------------------------------------------------------------
# User-routing helpers (mirrors the Task 5 series-file conventions)
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


def _fake_resolver() -> tuple[MagicMock, ResolvedModel]:
    """A spec'd fake resolver whose resolve() returns the user's model."""
    resolved = ResolvedModel(
        config=_user_config(),
        api_key=_USER_KEY,
        base_url=_USER_BASE_URL,
    )
    resolver = MagicMock(spec=ModelRoutingResolverImpl, name="ModelRoutingResolver")
    resolver.resolve = AsyncMock(return_value=resolved)
    return resolver, resolved


class TestGetWikiRepository:
    """get_wiki_repository(session) — creates WikiRepository."""

    def test_returns_wiki_repository(self) -> None:
        """Returns WikiRepository wrapping the given session."""
        mock_session = AsyncMock(spec=AsyncSession)
        repo = get_wiki_repository(mock_session)
        assert isinstance(repo, WikiRepository)
        assert repo._session is mock_session


class TestMakeSystemWikiFactory:
    """make_system_wiki_factory(core_service) — system-mode factory closure."""

    def test_factory_creates_system_service(self) -> None:
        """Factory closure creates APIWikiService with system_mode=True."""
        core_service = FakeCoreWikiService()
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("narrare._app.database._async_session_factory", return_value=mock_session):
            factory_fn = make_system_wiki_factory(core_service)
            svc = factory_fn()

        assert isinstance(svc, APIWikiService)
        assert svc._system_mode is True

    def test_factory_uses_captured_core_service(self) -> None:
        """Factory uses the same core_service passed to make_system_wiki_factory."""
        core_service = FakeCoreWikiService()
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("narrare._app.database._async_session_factory", return_value=mock_session):
            factory_fn = make_system_wiki_factory(core_service)
            svc = factory_fn()

        assert svc._core is core_service

    def test_factory_creates_fresh_service_per_call(self) -> None:
        """Each factory call creates a new APIWikiService instance."""
        core_service = FakeCoreWikiService()
        mock_session_1 = AsyncMock(spec=AsyncSession)
        mock_session_2 = AsyncMock(spec=AsyncSession)

        with patch(
            "narrare._app.database._async_session_factory",
            side_effect=[mock_session_1, mock_session_2],
        ):
            factory_fn = make_system_wiki_factory(core_service)
            svc_1 = factory_fn()
            svc_2 = factory_fn()

        assert svc_1 is not svc_2


class TestBuildCoreWikiService:
    """build_core_wiki_service() — core WikiService factory."""

    async def test_creates_and_returns_wiki_service(self) -> None:
        """build_core_wiki_service creates WikiService with agent and NullEventBus.

        Tests the full assembly chain: model_registry → config → model →
        WikiGenerationAgent → WikiService.
        """
        mock_model = AsyncMock()
        mock_registry = MagicMock(spec=ModelRegistry)
        mock_registry.prepare = AsyncMock(
            return_value=PreparedModelCall(model=mock_model, model_settings=None, usage_limits=None)
        )
        mock_config = MagicMock(spec=ResolvedModelConfig)

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
            patch(
                "narrare._app.dependencies_services.build_system_default_config",
                return_value=mock_config,
            ),
            patch("narrare_core.wiki.agent.WikiGenerationAgent") as mock_agent_cls,
            patch("narrare_core.wiki.service.WikiService") as mock_svc_cls,
            patch("narrare_core.events.bus.NullEventBus") as mock_bus_cls,
        ):
            mock_agent = mock_agent_cls.return_value
            mock_bus = mock_bus_cls.return_value
            mock_svc = mock_svc_cls.return_value

            result = await build_core_wiki_service()

            # Verify model resolved via the single assembly point (Task 6d)
            mock_registry.prepare.assert_awaited_once_with(mock_config, intent=LLMIntent.SUMMARIZE)

            # Verify agent created with model
            mock_agent_cls.assert_called_once_with(model=mock_model)

            # Verify event bus created
            mock_bus_cls.assert_called_once_with()

            # Verify service created with agent + event bus + optional pipeline
            mock_svc_cls.assert_called_once_with(
                agent=mock_agent, event_bus=mock_bus, invocation_pipeline=None
            )

            # Verify return value
            assert result is mock_svc

    async def test_user_plane_skips_system_default_and_threads_credentials(self) -> None:
        """User plane: resolved config + credentials reach prepare().

        When a resolved config is provided, ``build_core_wiki_service``
        must NOT touch ``build_system_default_config`` (operator plane)
        and must thread api_key/base_url + the site intent into the
        single assembly point (Task 6d).
        """
        mock_model = AsyncMock()
        mock_registry = MagicMock(spec=ModelRegistry)
        mock_registry.prepare = AsyncMock(
            return_value=PreparedModelCall(model=mock_model, model_settings=None, usage_limits=None)
        )
        config = _user_config()

        with (
            patch("narrare._app.dependencies.get_model_registry", return_value=mock_registry),
            patch(
                "narrare._app.dependencies_services.build_system_default_config"
            ) as mock_system_config,
            patch("narrare_core.wiki.agent.WikiGenerationAgent"),
            patch("narrare_core.wiki.service.WikiService"),
        ):
            result = await build_core_wiki_service(
                config=config, api_key=_USER_KEY, base_url=_USER_BASE_URL
            )

        mock_registry.prepare.assert_awaited_once_with(
            config,
            intent=LLMIntent.SUMMARIZE,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )
        mock_system_config.assert_not_called()
        assert result is not None


class TestGetWikiServiceUserRouting:
    """get_wiki_service resolves via the cascade (SUMMARIZE, project tier)."""

    async def test_resolves_summarize_for_user_with_project_tier(self) -> None:
        """The user-facing factory resolves SUMMARIZE for user + novel.

        All wiki routes are novel-scoped, so the novel_id path parameter
        IS available at dependency-wiring time and threads into resolve()
        as the cascade's project tier.
        """
        mock_session = AsyncMock(spec=AsyncSession)
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.wiki.dependencies.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare.wiki.dependencies.build_core_wiki_service",
                new_callable=AsyncMock,
            ) as mock_build_core,
            patch(
                "narrare.wiki.dependencies.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ) as mock_pipeline,
            patch("narrare.chapters.repository.ChapterRepository"),
            patch("narrare.novels.repository.NovelRepository"),
            patch("narrare.kb.repository.KBRepository"),
            patch("narrare.kb.relationship_repository.RelationshipRepository"),
            patch("narrare.wiki.repository.WikiRepository"),
            patch("narrare.wiki.chapter_service.ChapterWikiService"),
            patch("narrare.wiki.service.APIWikiService"),
        ):
            await get_wiki_service(novel_id=novel_id, session=mock_session, user_id=user_id)

        resolver.resolve.assert_awaited_once_with(LLMIntent.SUMMARIZE, UUID(user_id), novel_id)
        mock_build_core.assert_awaited_once_with(
            invocation_pipeline=mock_pipeline.return_value,
            config=resolved.config,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )


class TestGetWikiService:
    """get_wiki_service(session) — APIWikiService factory."""

    async def test_wires_all_dependencies_and_returns_api_service(self) -> None:
        """get_wiki_service creates APIWikiService with all deps wired.

        Tests that all repositories, chapter service, and core
        service are created and passed to APIWikiService correctly.
        """
        mock_session = AsyncMock(spec=AsyncSession)
        mock_core_service = MagicMock(spec=FakeCoreWikiService)
        resolver, _resolved = _fake_resolver()

        with (
            patch(
                "narrare.wiki.dependencies.get_model_routing_resolver",
                return_value=resolver,
            ),
            patch(
                "narrare.wiki.dependencies.build_core_wiki_service",
                new_callable=AsyncMock,
                return_value=mock_core_service,
            ),
            patch(
                "narrare._app.dependencies.get_invocation_pipeline",
                return_value=MagicMock(spec=True, name="InvocationPipeline"),
            ),
            patch("narrare.chapters.repository.ChapterRepository") as mock_chapter_repo_cls,
            patch("narrare.novels.repository.NovelRepository") as mock_novel_repo_cls,
            patch("narrare.kb.repository.KBRepository") as mock_kb_repo_cls,
            patch("narrare.kb.relationship_repository.RelationshipRepository") as mock_rel_repo_cls,
            patch("narrare.wiki.repository.WikiRepository") as mock_wiki_repo_cls,
            patch("narrare.wiki.chapter_service.ChapterWikiService") as mock_chapter_svc_cls,
            patch("narrare.wiki.service.APIWikiService") as mock_api_svc_cls,
        ):
            mock_chapter_svc = mock_chapter_svc_cls.return_value
            mock_api_svc = mock_api_svc_cls.return_value

            result = await get_wiki_service(
                novel_id=uuid4(), session=mock_session, user_id=str(uuid4())
            )

            # Verify ChapterWikiService constructed with correct deps
            mock_chapter_svc_cls.assert_called_once_with(
                wiki_repo=mock_wiki_repo_cls.return_value,
                novel_repo=mock_novel_repo_cls.return_value,
                chapter_repo=mock_chapter_repo_cls.return_value,
                core_wiki_service=mock_core_service,
            )

            # Verify APIWikiService constructed with all deps
            mock_api_svc_cls.assert_called_once_with(
                session=mock_session,
                wiki_repo=mock_wiki_repo_cls.return_value,
                kb_repo=mock_kb_repo_cls.return_value,
                novel_repo=mock_novel_repo_cls.return_value,
                relationship_repo=mock_rel_repo_cls.return_value,
                core_wiki_service=mock_core_service,
                chapter_wiki_service=mock_chapter_svc,
                chapter_repo=mock_chapter_repo_cls.return_value,
                model_registry=None,
                model_routing_resolver=None,
                system_mode=False,
            )

            assert result is mock_api_svc
