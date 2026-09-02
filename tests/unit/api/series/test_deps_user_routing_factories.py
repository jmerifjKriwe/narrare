"""User-routing migration tests — Task 5 series factories.

Mirrors ``tests/unit/api/analysis/test_deps_user_routing_voice_factories.py``
(Task 2b conventions). Proves that each series factory resolves via the
per-user ``ModelRoutingResolver`` cascade with the correct intent + user_id
and that the resolved config + credentials reach the service AND its ACTUAL
``get_model`` resolution points:

- ``get_series_voice_service`` (VOICE — ``author_voice_prompt`` composes with
  ``intent=LLMIntent.VOICE``)
- ``get_series_consistency_service`` (ANALYSE — ``series_consistency_prompt``
  composes with ``intent=LLMIntent.ANALYSE``)
- ``get_series_voice_drift_service`` (VOICE — ``author_voice_drift_prompt``
  composes with ``intent=LLMIntent.VOICE``)

Tier decision: all three resolve WITHOUT the project tier (``project_id=None``).
The series routes are series-scoped (``/series/{series_id}/...``); the novel id
— the cascade's project tier key — arrives only in the request BODY (voice
profile / consistency check / voice-drift check) or not at all (the remaining
voice + snapshot endpoints), so it is never available at dependency-wiring
time. Passing the SERIES id as the project id would query the
project-routing table with a foreign UUID (series ids are not project/novel
ids). Same documented caveat as ``dependencies_context_preview.py``
(SERIES-002): user/operator-level routing + cascade overrides apply.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

if TYPE_CHECKING:
    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

# ---------------------------------------------------------------------------
# Shared helpers (mirrors the Task 2b analysis-file conventions)
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


class _StopResolution(BaseException):
    """Sentinel raised after get_model recorded its call (short-circuits run).

    ``BaseException`` (not ``Exception``) so the services' broad
    ``except Exception`` error wrappers (RULE-11) cannot swallow it into a
    ``WritingError``.
    """


class _RecordingRegistry:
    """Fake ModelRegistry — records ``get_model`` calls for assertions."""

    def __init__(self, stop_after_record: BaseException | None = None) -> None:
        self.calls: list[dict[str, object]] = []
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


# ===========================================================================
# Factory wiring — resolve() via the cascade, credentials land on the service
# ===========================================================================


class TestSeriesVoiceFactoryUserRouting:
    """get_series_voice_service resolves via the cascade (VOICE, no project)."""

    async def test_resolves_voice_for_user_without_project_tier(self) -> None:
        from narrare.series.dependencies_voice import get_series_voice_service
        from narrare.series.series_voice_service import SeriesVoiceService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.series.dependencies_voice.get_model_routing_resolver",
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
            service = await get_series_voice_service(
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.VOICE, UUID(user_id), None)
        assert isinstance(service, SeriesVoiceService)
        assert service._config is resolved.config
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL


class TestSeriesConsistencyFactoryUserRouting:
    """get_series_consistency_service resolves via the cascade (ANALYSE)."""

    async def test_resolves_analyse_for_user_without_project_tier(self) -> None:
        from narrare.series.dependencies_consistency import get_series_consistency_service
        from narrare.series.series_consistency_service import SeriesConsistencyService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.series.dependencies_consistency.get_model_routing_resolver",
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
            service = await get_series_consistency_service(
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.ANALYSE, UUID(user_id), None)
        assert isinstance(service, SeriesConsistencyService)
        assert service._config is resolved.config
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL


class TestSeriesVoiceDriftFactoryUserRouting:
    """get_series_voice_drift_service resolves via the cascade (VOICE)."""

    async def test_resolves_voice_for_user_without_project_tier(self) -> None:
        from narrare.series.dependencies_voice_drift import get_series_voice_drift_service
        from narrare.series.series_voice_drift_service import SeriesVoiceDriftService

        session = MagicMock(spec=AsyncSession, name="session")
        user_id = str(uuid4())
        resolver, resolved = _fake_resolver()

        with (
            patch(
                "narrare.series.dependencies_voice_drift.get_model_routing_resolver",
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
            service = await get_series_voice_drift_service(
                session=session,
                user_id=user_id,
            )

        resolver.resolve.assert_awaited_once_with(LLMIntent.VOICE, UUID(user_id), None)
        assert isinstance(service, SeriesVoiceDriftService)
        assert service._config is resolved.config
        assert service._api_key == _USER_KEY
        assert service._base_url == _USER_BASE_URL


# ===========================================================================
# Resolution point — credentials reach the services' ACTUAL get_model calls
# ===========================================================================


class TestSeriesCredentialsReachResolutionPoint:
    """The resolved key must flow into each service's ACTUAL get_model call."""

    async def test_series_voice_service_threads_credentials_into_get_model(self) -> None:
        from narrare.series.series_voice_service import SeriesVoiceService
        from tests.fakes.fake_chapter_repo import FakeChapterRepository
        from tests.fakes.fake_novel_repo import FakeNovelRepository
        from tests.fakes.fake_series_repo import FakeSeriesRepository

        from ._series_voice_drift_test_helpers import seed_owned_series
        from ._series_voice_test_helpers import patch_author_voice_pipeline

        user_id = uuid4()
        series_repo, novel_repo, chapter_repo = (
            FakeSeriesRepository(),
            FakeNovelRepository(),
            FakeChapterRepository(),
        )
        series_id, novel_id = seed_owned_series(
            series_repo,
            novel_repo,
            chapter_repo,
            user_id=user_id,
        )

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service = SeriesVoiceService(
            series_repo=cast("SeriesRepositoryProtocol", series_repo),
            novel_repo=cast("NovelRepositoryProtocol", novel_repo),
            chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
            model_registry=cast("ModelRegistry", registry),
            model_config=config,
            composer=cast("PromptComposer", MagicMock(spec=["build"], name="PromptComposer")),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        # get_model raises the sentinel through the (real) shared agent runner
        # — proving the credentials travel factory → service → get_model.
        with patch_author_voice_pipeline(), pytest.raises(_StopResolution):
            await service.profile_from_novel(series_id, novel_id, user_id)

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]

    async def test_series_consistency_service_threads_credentials_into_get_model(self) -> None:
        from narrare.series.series_consistency_service import SeriesConsistencyService
        from tests.fakes.fake_chapter_repo import FakeChapterRepository
        from tests.fakes.fake_kb_scope_repo import FakeScopeKBRepo
        from tests.fakes.fake_novel_repo import FakeNovelRepository
        from tests.fakes.fake_series_repo import FakeSeriesRepository

        from ._series_consistency_test_helpers import (
            FakeSeriesConsistencyComposer,
            seed_owned_series_with_canon,
        )

        user_id = uuid4()
        series_repo, novel_repo, chapter_repo = (
            FakeSeriesRepository(),
            FakeNovelRepository(),
            FakeChapterRepository(),
        )
        kb_repo = FakeScopeKBRepo()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service = SeriesConsistencyService(
            series_repo=cast("SeriesRepositoryProtocol", series_repo),
            novel_repo=cast("NovelRepositoryProtocol", novel_repo),
            chapter_repo=cast("ChapterRepositoryProtocol", chapter_repo),
            kb_repo=cast("KBRepositoryProtocol", kb_repo),
            registry=cast("ModelRegistry", registry),
            config=config,
            composer=cast("PromptComposer", FakeSeriesConsistencyComposer()),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        # The sentinel escapes the service's broad RULE-11 error wrapper
        # (BaseException) — proving the credentials reach the real get_model.
        with pytest.raises(_StopResolution):
            await service.check_novel(series_id, novel_id, user_id)

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]

    async def test_series_voice_drift_service_threads_credentials_into_get_model(self) -> None:
        from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
        from narrare.series.series_voice_drift_service import SeriesVoiceDriftService
        from tests.fakes.fake_chapter_repo import FakeChapterRepository
        from tests.fakes.fake_novel_repo import FakeNovelRepository
        from tests.fakes.fake_series_repo import FakeSeriesRepository

        from ._series_voice_drift_test_helpers import (
            make_author_profile,
            patch_mode1,
            seed_owned_series,
            seed_series_voice,
        )

        user_id = uuid4()
        series_repo, novel_repo, chapter_repo = (
            FakeSeriesRepository(),
            FakeNovelRepository(),
            FakeChapterRepository(),
        )
        series_id, novel_id = seed_owned_series(
            series_repo,
            novel_repo,
            chapter_repo,
            user_id=user_id,
        )
        await seed_series_voice(series_repo, series_id, make_author_profile())

        config = _user_config()
        registry = _RecordingRegistry(stop_after_record=_StopResolution())
        service = SeriesVoiceDriftService(
            series_repo=cast("SeriesRepositoryProtocol", series_repo),
            novel_repo=cast("NovelRepositoryProtocol", novel_repo),
            chapter_repo=cast("ChapterRepository", chapter_repo),
            model_registry=cast("ModelRegistry", registry),
            model_config=config,
            composer=cast("PromptComposer", MagicMock(spec=["build"], name="PromptComposer")),
            api_key=_USER_KEY,
            base_url=_USER_BASE_URL,
        )

        with patch_mode1(), pytest.raises(_StopResolution):
            await service.check(series_id, novel_id, user_id, AuthorVoiceDriftRequest())

        assert registry.calls == [
            {"config": config, "api_key": _USER_KEY, "base_url": _USER_BASE_URL}
        ]
