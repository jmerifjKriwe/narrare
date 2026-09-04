"""User-routing migration tests for kb dependency factories (Task 1a).

Regression-first proof that the kb extraction/improve factories resolve the
model via the per-user ``ModelRoutingResolver`` cascade (instead of the legacy
``build_system_default_config``) with the correct intent + user_id + novel_id,
and that the resolved config + api_key/base_url reach the ACTUAL resolution
point inside the services (``ModelRegistry.prepare`` for extraction,
``ModelRegistry.get_model`` for the improve analyzer until its Task 6
migration).

Pattern reference: ``tests/unit/api/writing/test_deps_factories_summary.py``.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

if TYPE_CHECKING:
    from pydantic_ai.models import Model
    from pydantic_ai.usage import UsageLimits

    from narrare_core.llm.gateway import ModelRegistry

# ---------------------------------------------------------------------------
# Shared helpers
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


class _StopResolution(Exception):
    """Sentinel raised after get_model recorded its call (short-circuits run)."""


class _RecordingRegistry:
    """Fake ModelRegistry — records ``prepare``/``get_model`` calls for assertions."""

    def __init__(self, stop_after_record: BaseException | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.prepares: list[dict[str, object]] = []
        self._stop = stop_after_record

    async def get_model(
        self,
        config: ResolvedModelConfig,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        usage_limits: object = None,
    ) -> object:
        self.calls.append({"config": config, "api_key": api_key, "base_url": base_url})
        if self._stop is not None:
            raise self._stop
        return SimpleNamespace(sentinel_model=True)

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: LLMIntent | None = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        self.prepares.append(
            {"config": config, "intent": intent, "api_key": api_key, "base_url": base_url}
        )
        model = await self.get_model(config, api_key=api_key, base_url=base_url)
        return PreparedModelCall(
            model=cast("Model", model), model_settings=None, usage_limits=usage_limits
        )


# ===========================================================================
# Structural — factories are async, user-scoped, legacy-pattern-free
# ===========================================================================


class TestFactoryStructure:
    """Structural regressions: signature gains user routing, legacy is gone."""

    def test_get_extraction_service_is_async_with_user_routing_params(self) -> None:
        from narrare.kb.dependencies_extraction import get_extraction_service

        assert inspect.iscoroutinefunction(get_extraction_service)
        params = list(inspect.signature(get_extraction_service).parameters)
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    def test_get_kb_improve_service_is_async_with_user_routing_params(self) -> None:
        from narrare.kb.dependencies_improve import get_kb_improve_service

        assert inspect.iscoroutinefunction(get_kb_improve_service)
        params = list(inspect.signature(get_kb_improve_service).parameters)
        assert "user_id" in params
        assert "novel_id" in params
        assert "session" in params

    def test_extraction_factory_does_not_use_system_default_config(self) -> None:
        import narrare.kb.dependencies_extraction as mod

        source = inspect.getsource(mod)
        assert "build_system_default_config" not in source
        assert "SystemModelCategory" not in source

    def test_improve_factory_does_not_use_system_default_config(self) -> None:
        import narrare.kb.dependencies_improve as mod

        source = inspect.getsource(mod)
        assert "build_system_default_config" not in source
        assert "SystemModelCategory" not in source


# ===========================================================================
# Factory execution — resolver resolves with intent + user_id + novel_id
# ===========================================================================


class TestExtractionFactoryUserRouting:
    """get_extraction_service resolves via the cascade (KB_EXTRACT)."""

    async def test_resolves_kb_extract_for_user_and_novel(self) -> None:
        from narrare.kb.dependencies_extraction import get_extraction_service
        from narrare.kb.extraction_service import ExtractionService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.kb.dependencies_extraction.get_model_routing_resolver",
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
            service = await get_extraction_service(
                novel_id=novel_id,
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.KB_EXTRACT, UUID(user_id), novel_id)
        assert isinstance(service, ExtractionService)
        assert service._config is resolved.config
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL


class TestImproveFactoryUserRouting:
    """get_kb_improve_service resolves via the cascade (KB_IMPROVE)."""

    async def test_resolves_kb_improve_for_user_and_novel(self) -> None:
        from narrare.kb.dependencies_improve import get_kb_improve_service
        from narrare.kb.improve_service import KBImproveService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        novel_id = uuid4()
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.kb.dependencies_improve.get_model_routing_resolver",
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
            service = await get_kb_improve_service(
                novel_id=novel_id,
                session=session,
                event_publisher=MagicMock(spec=True, name="WikiEventPublisher"),
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.KB_IMPROVE, UUID(user_id), novel_id)
        assert isinstance(service, KBImproveService)
        assert service._analyzer._config is resolved.config
        assert service._analyzer._api_key == _USER_KEY
        assert service._analyzer._base_url == _USER_BASE_URL


# ===========================================================================
# Resolution point — credentials reach ModelRegistry.prepare
# ===========================================================================


class TestCredentialsReachResolutionPoint:
    """The resolved key must flow into the ACTUAL prepare() call (setup bug)."""

    async def test_extraction_service_threads_credentials_into_prepare(self) -> None:
        from narrare.kb.extraction_service import ExtractionService

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        composer = MagicMock(spec=["build"], name="PromptComposer")
        composer.build = AsyncMock(return_value=SimpleNamespace(system="system prompt"))
        chapter_repo = MagicMock(spec=["get_by_id"], name="ChapterRepository")
        chapter_repo.get_by_id = AsyncMock(
            return_value=SimpleNamespace(title="Chapter 1", content="Once upon a time.")
        )
        kb_repo = MagicMock(spec=["list_entries"], name="KBRepository")
        kb_repo.list_entries = AsyncMock(return_value=([], 0))

        service = ExtractionService(
            registry=cast("ModelRegistry", registry),
            config=config,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            composer=composer,
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        with pytest.raises(_StopResolution):
            await service.extract_from_chapter(
                novel_id=uuid4(), chapter_id=uuid4(), user_id=uuid4()
            )

        # Resolution goes through prepare() with the KB intent + credentials.
        assert len(registry.prepares) == 1
        prepared = registry.prepares[0]
        assert prepared["config"] is config
        assert prepared["intent"] is LLMIntent.KB_EXTRACT
        assert prepared["api_key"] == _USER_KEY
        assert prepared["base_url"] == _USER_BASE_URL

        # Exactly ONE get_model resolution (via prepare) — the historical
        # duplicate direct get_model call is dead.
        assert len(registry.calls) == 1
        call = registry.calls[0]
        assert call["config"] is config
        assert call["api_key"] == _USER_KEY
        assert call["base_url"] == _USER_BASE_URL

    async def test_improve_analyzer_threads_credentials_into_prepare(self) -> None:
        from narrare.kb.improve_analyzer import KBImproveAnalyzer

        config = _user_config()
        registry = _RecordingRegistry()
        analyzer = KBImproveAnalyzer(
            registry=cast("ModelRegistry", registry),
            config=config,
            kb_context_provider=MagicMock(spec=True, name="KBContextProvider"),
            prompt_composer=MagicMock(spec=True, name="PromptComposer"),
            kb_repo=MagicMock(spec=True, name="KBRepository"),
            rel_repo=MagicMock(spec=True, name="RelationshipRepository"),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        prepared = await analyzer._prepare()

        # Credentials + intent reach the single assembly point (Task 6c
        # resolution point), and the delegated get_model got the credentials.
        assert registry.prepares == [
            {
                "config": config,
                "intent": LLMIntent.KB_IMPROVE,
                "api_key": _USER_KEY,
                "base_url": _USER_BASE_URL,
            }
        ]
        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]
        assert getattr(prepared.model, "sentinel_model", False) is True
